import io
import struct
import zlib

import anyio
from fastapi.testclient import TestClient
from PIL import Image
from PIL.ExifTags import Base

from application.errors import PayloadTooLargeError, UnsupportedMediaTypeError
from application.gateways import AuthUser
from application.media_storage import S3MediaStorage, prepare_photo_upload
from application.photo_normalize import PHOTO_ENCODE_QUALITY, PHOTO_MAX_EDGE_PX
from presentation.http.main import app

_SECRET = b"secret-camera-serial-XYZ"


def _save(image: Image.Image, fmt: str, **params: object) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format=fmt, **params)
    return buffer.getvalue()


def _jpeg(
    width: int,
    height: int,
    *,
    color: tuple[int, int, int] = (20, 40, 80),
    exif: Image.Exif | None = None,
) -> bytes:
    image = Image.new("RGB", (width, height), color)
    params: dict[str, object] = {"quality": 95}
    if exif is not None:
        params["exif"] = exif
    return _save(image, "JPEG", **params)


def _open(data: bytes) -> Image.Image:
    image = Image.open(io.BytesIO(data))
    image.load()
    return image


def _png_header(width: int, height: int) -> bytes:
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    chunk_type = b"IHDR"
    crc = zlib.crc32(chunk_type + ihdr) & 0xFFFFFFFF
    ihdr_chunk = struct.pack(">I", len(ihdr)) + chunk_type + ihdr + struct.pack(">I", crc)
    iend_type = b"IEND"
    iend_crc = zlib.crc32(iend_type) & 0xFFFFFFFF
    iend_chunk = struct.pack(">I", 0) + iend_type + struct.pack(">I", iend_crc)
    return signature + ihdr_chunk + iend_chunk


def test_quality_and_edge_stay_in_the_requested_range() -> None:
    assert PHOTO_MAX_EDGE_PX == 1600
    assert 75 <= PHOTO_ENCODE_QUALITY <= 85


def test_downscale_keeps_aspect_and_does_not_crop_to_four_by_three() -> None:
    wide = prepare_photo_upload("wide.jpg", _jpeg(3200, 800), max_bytes=8 * 1024 * 1024)
    data, extension, content_type = wide
    assert extension == ".jpg"
    assert content_type == "image/jpeg"
    with _open(data) as image:
        assert image.size == (1600, 400)
        assert image.mode == "RGB"

    four_by_three = prepare_photo_upload("pose.jpg", _jpeg(2000, 1500), max_bytes=8 * 1024 * 1024)[0]
    with _open(four_by_three) as image:
        assert image.size == (1600, 1200)


def test_small_photo_is_not_upscaled() -> None:
    data, extension, _content_type = prepare_photo_upload("tiny.jpeg", _jpeg(80, 60), max_bytes=1024 * 1024)
    assert extension == ".jpg"
    with _open(data) as image:
        assert image.size == (80, 60)


def _near(pixel: tuple[int, ...], expected: tuple[int, int, int], *, tolerance: int = 12) -> bool:
    return all(abs(channel - target) <= tolerance for channel, target in zip(pixel, expected, strict=True))


def test_exif_orientation_is_applied_and_metadata_is_stripped() -> None:
    # Крупные поля цвета: одиночный пиксель JPEG размазывает, центр блока — нет.
    stored = Image.new("RGB", (80, 40), (0, 0, 255))
    stored.paste(Image.new("RGB", (40, 40), (255, 0, 0)), (0, 0))
    exif = stored.getexif()
    exif[Base.Orientation] = 6
    exif[Base.ImageDescription] = _SECRET.decode()
    raw = _save(stored, "JPEG", quality=95, exif=exif)
    assert _SECRET in raw

    normalized, extension, content_type = prepare_photo_upload("phone.jpg", raw, max_bytes=1024 * 1024)
    assert extension == ".jpg"
    assert content_type == "image/jpeg"
    assert _SECRET not in normalized
    expected = stored.transpose(Image.Transpose.ROTATE_270)
    # Центры красной и синей половин после поворота на 90° по часовой.
    assert expected.getpixel((20, 20)) == (255, 0, 0)
    assert expected.getpixel((20, 60)) == (0, 0, 255)
    with _open(normalized) as image:
        assert image.size == expected.size == (40, 80)
        assert _near(image.getpixel((20, 20)), (255, 0, 0))
        assert _near(image.getpixel((20, 60)), (0, 0, 255))
        assert Base.ImageDescription not in image.getexif()
        assert image.getexif().get(Base.Orientation, 1) == 1


def test_png_is_reencoded_as_jpeg_and_alpha_becomes_white() -> None:
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    image.paste(Image.new("RGBA", (32, 64), (255, 0, 0, 255)), (0, 0))
    raw = _save(image, "PNG")
    data, extension, content_type = prepare_photo_upload("end.png", raw, max_bytes=1024 * 1024)
    assert extension == ".jpg"
    assert content_type == "image/jpeg"
    assert data[:3] == b"\xff\xd8\xff"
    with _open(data) as decoded:
        assert decoded.size == (64, 64)
        assert decoded.mode == "RGB"
        assert _near(decoded.getpixel((16, 32)), (255, 0, 0))
        assert _near(decoded.getpixel((48, 32)), (255, 255, 255))


def test_webp_stays_webp_and_keeps_alpha() -> None:
    image = Image.new("RGBA", (12, 8), (10, 20, 30, 128))
    raw = _save(image, "WEBP", quality=90)
    data, extension, content_type = prepare_photo_upload("start.webp", raw, max_bytes=1024 * 1024)
    assert extension == ".webp"
    assert content_type == "image/webp"
    assert data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    with _open(data) as decoded:
        assert decoded.size == (12, 8)
        assert decoded.mode == "RGBA"
        assert decoded.getpixel((1, 1))[3] < 255


def test_cmyk_jpeg_becomes_rgb() -> None:
    raw = _save(Image.new("CMYK", (5, 7), (0, 0, 0, 0)), "JPEG", quality=90)
    data, extension, _content_type = prepare_photo_upload("shot.jpeg", raw, max_bytes=1024 * 1024)
    assert extension == ".jpg"
    with _open(data) as image:
        assert image.mode == "RGB"
        assert image.size == (5, 7)


def test_corrupt_and_oversized_and_huge_dimensions_are_rejected() -> None:
    try:
        prepare_photo_upload("shot.jpg", b"\xff\xd8\xff\xe0" + b"not-a-jpeg", max_bytes=1024)
    except UnsupportedMediaTypeError as exc:
        assert "corrupt" in str(exc)
    else:
        raise AssertionError("corrupt jpeg should be rejected")

    tiny = _jpeg(4, 4)
    try:
        prepare_photo_upload("shot.jpg", tiny, max_bytes=8)
    except PayloadTooLargeError as exc:
        assert "too large" in str(exc)
    else:
        raise AssertionError("oversized upload should be rejected")

    try:
        prepare_photo_upload("bomb.png", _png_header(20_000, 20_000), max_bytes=1024 * 1024)
    except PayloadTooLargeError as exc:
        assert "dimensions" in str(exc)
    else:
        raise AssertionError("huge declared dimensions should be rejected")


class _CapturingStorage(S3MediaStorage):
    def __init__(self) -> None:
        super().__init__(
            endpoint="minio:9000",
            access_key="photos-videos-only",
            secret_key="secret",
            bucket="fitboddy-media",
            secure=False,
        )
        self.saved: dict[str, tuple[bytes, str]] = {}
        self.puts = 0

    def _put_object_sync(self, object_name: str, data: bytes, content_type: str) -> None:
        self.puts += 1
        self.saved[object_name] = (data, content_type)


def test_upload_photo_stores_normalized_bytes_not_the_original() -> None:
    storage = _CapturingStorage()
    raw = _jpeg(2400, 900)

    async def _upload() -> str:
        return await storage.upload_photo(
            owner_id="trainer_norm",
            row_id="row_norm",
            filename="start.jpg",
            data=raw,
            position="start",
        )

    key = anyio.run(_upload)
    assert key in storage.saved
    assert key.endswith(".jpg")
    assert key.startswith("photos/trainer_norm/row_norm/start/")
    body, content_type = storage.saved[key]
    assert content_type == "image/jpeg"
    assert body != raw
    with _open(body) as image:
        assert image.size == (1600, 600)


def test_upload_photo_does_not_store_a_corrupt_file() -> None:
    storage = _CapturingStorage()

    async def _upload() -> str:
        return await storage.upload_photo(
            owner_id="trainer_norm",
            row_id="row_norm",
            filename="start.jpg",
            data=b"\xff\xd8\xff" + b"garbage",
            position="end",
        )

    try:
        anyio.run(_upload)
    except UnsupportedMediaTypeError:
        pass
    else:
        raise AssertionError("corrupt upload should fail before put")
    assert storage.puts == 0


def _client() -> TestClient:
    return TestClient(app)


def _auth(user_id: str, *, role: str) -> dict[str, str]:
    runtime = app.state.plan_handler._runtime
    runtime.auth_gateway.get_current_user = lambda _token: AuthUser(
        user_id=user_id,
        tenant_id="tenant_1",
        role=role,
    )
    runtime.tenant_gateway.get_client_active_trainer_id = lambda client_id: None
    return {"Authorization": "Bearer test-user-token"}


def _as_admin() -> dict[str, str]:
    runtime = app.state.plan_handler._runtime
    runtime.auth_gateway.require_platform_admin = lambda _token: AuthUser(
        user_id="admin_1",
        tenant_id="platform",
        role="platform_admin",
    )
    return {"Authorization": "Bearer test-admin-token"}


def _signed_object_key(url: str) -> str:
    path = url.split("?", 1)[0]
    prefix = "/api/v1/trainers/media/"
    assert path.startswith(prefix)
    return path[len(prefix) :]


def test_start_and_end_photo_routes_store_normalized_images() -> None:
    storage = _CapturingStorage()
    trainer_user_id = "trainer_photo_normalize"
    with _client() as client:
        runtime = app.state.plan_handler._runtime
        previous = runtime._video_storage
        runtime._video_storage = storage
        try:
            created = client.post(
                f"/api/v1/trainers/{trainer_user_id}/exercises",
                headers=_auth(trainer_user_id, role="trainer"),
                json={
                    "exercise_name": "Normalized Photo",
                    "equipment": "none",
                    "is_cardio": False,
                    "is_hold": False,
                    "difficulty": 1,
                    "workout_category": "full_body",
                },
            )
            assert created.status_code == 201
            row_id = created.json()["row_id"]
            assert created.json()["start_image_url"] is None
            assert created.json()["end_image_url"] is None

            uploaded = client.post(
                f"/api/v1/trainers/{trainer_user_id}/exercises/{row_id}/photos/start",
                headers=_auth(trainer_user_id, role="trainer"),
                files={"file": ("start.jpg", _jpeg(2400, 1800), "image/jpeg")},
            )
            assert uploaded.status_code == 200, uploaded.text
            start_key = _signed_object_key(uploaded.json()["image_url"])
            assert uploaded.json()["position"] == "start"
            body, content_type = storage.saved[start_key]
            assert content_type == "image/jpeg"
            with _open(body) as image:
                assert image.size == (1600, 1200)

            listed = client.get(
                f"/api/v1/trainers/{trainer_user_id}/exercises",
                headers=_auth(trainer_user_id, role="trainer"),
            )
            item = next(row for row in listed.json() if row["row_id"] == row_id)
            assert _signed_object_key(item["start_image_url"]) == start_key
            assert item["end_image_url"] is None

            corrupt = client.post(
                f"/api/v1/trainers/{trainer_user_id}/exercises/{row_id}/photos/end",
                headers=_auth(trainer_user_id, role="trainer"),
                files={"file": ("end.jpg", b"\xff\xd8\xff\xe0" + b"broken", "image/jpeg")},
            )
            assert corrupt.status_code == 415
            assert storage.puts == 1

            _as_admin()
            platform = client.post(
                "/api/v1/admin/platform-exercises",
                headers=_as_admin(),
                json={
                    "exercise_name": "Normalized Platform Photo",
                    "equipment": "none",
                    "is_cardio": False,
                    "is_hold": False,
                    "difficulty": 1,
                    "workout_category": "full_body",
                    "catalog_key": "normalized_platform_photo",
                },
            )
            assert platform.status_code == 201, platform.text
            platform_id = platform.json()["row_id"]
            png = Image.new("RGB", (1800, 600), (30, 60, 90))
            end_upload = client.post(
                f"/api/v1/admin/platform-exercises/{platform_id}/photos/end",
                headers=_as_admin(),
                files={"file": ("end.png", _save(png, "PNG"), "image/png")},
            )
            assert end_upload.status_code == 200, end_upload.text
            end_key = _signed_object_key(end_upload.json()["image_url"])
            assert end_key.endswith(".jpg")
            assert end_upload.json()["position"] == "end"
            end_body, end_type = storage.saved[end_key]
            assert end_type == "image/jpeg"
            with _open(end_body) as image:
                assert image.size == (1600, 533)
            detail = client.get(f"/api/v1/platform-exercises/{platform_id}")
            assert detail.status_code == 200
            assert detail.json()["start_image_url"] is None
            assert _signed_object_key(detail.json()["end_image_url"]) == end_key
        finally:
            runtime._video_storage = previous
