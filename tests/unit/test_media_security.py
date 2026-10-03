import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from application.errors import ForbiddenError, IntegrationError, UnsupportedMediaTypeError
from application.media_keys import normalize_stored_media
from application.media_storage import S3MediaStorage, detect_image_media_type, validate_photo_bytes
from application.media_urls import MediaUrlSigner

_ROOT = Path(__file__).resolve().parents[2]
_STORAGE_SOURCE = (_ROOT / "lib" / "application" / "media_storage.py").read_text()


def test_photo_magic_bytes_reject_extension_spoof() -> None:
    jpeg = b"\xff\xd8\xff\xe0" + b"payload"
    png = b"\x89PNG\r\n\x1a\n" + b"payload"
    webp = b"RIFF\x18\x00\x00\x00WEBP" + b"payload"
    assert detect_image_media_type(jpeg) == "image/jpeg"
    assert detect_image_media_type(png) == "image/png"
    assert detect_image_media_type(webp) == "image/webp"
    assert detect_image_media_type(b"GIF89a") is None
    extension, content_type = validate_photo_bytes("shot.jpeg", jpeg, max_bytes=1024)
    assert extension == ".jpeg"
    assert content_type == "image/jpeg"
    try:
        validate_photo_bytes("shot.jpg", png, max_bytes=1024)
    except UnsupportedMediaTypeError as exc:
        assert "does not match" in str(exc)
    else:
        raise AssertionError("spoofed jpeg should be rejected")


def test_signer_roundtrip_and_expiry() -> None:
    signer = MediaUrlSigner("secret", 300)
    signed = signer.sign("photos/platform/row/start/abc.jpg", now=1_700_000_000)
    assert signed is not None
    path, query = signed.split("?", 1)
    assert path == "/api/v1/trainers/media/photos/platform/row/start/abc.jpg"
    expires = query.split("&")[0].split("=", 1)[1]
    signature = query.split("signature=", 1)[1]
    assert signer.verify("photos/platform/row/start/abc.jpg", expires, signature, now=1_700_000_100) == int(expires)
    try:
        signer.verify("photos/platform/row/start/abc.jpg", expires, signature, now=1_700_000_000 + 301)
        raise AssertionError("expired signature should be rejected")
    except ForbiddenError as exc:
        assert "expired" in str(exc)
    try:
        signer.verify("photos/platform/row/start/abc.jpg", None, None, now=1_700_000_100)
        raise AssertionError("missing signature should be rejected")
    except ForbiddenError as exc:
        assert "missing" in str(exc)


def test_normalize_strips_legacy_media_url() -> None:
    assert (
        normalize_stored_media("/api/v1/trainers/media/photos/platform/row/start/abc.jpg?expires=1&signature=aa")
        == "photos/platform/row/start/abc.jpg"
    )


def test_storage_uses_only_object_get_put_delete_inside_prefixes() -> None:
    for forbidden in ("bucket_exists", "make_bucket", "list_buckets", "list_objects", "stat_object"):
        assert forbidden not in _STORAGE_SOURCE
    storage = S3MediaStorage(
        endpoint="minio:9000",
        access_key="photos-videos-only",
        secret_key="secret",
        bucket="fitboddy-media",
        secure=False,
    )
    storage._require_allowed_key("photos/platform/row/start/abc.jpg")
    storage._require_allowed_key("videos/trainer/row/abc.mp4")
    try:
        storage._require_allowed_key("other/secret.txt")
        raise AssertionError("key outside photos/ and videos/ must be rejected")
    except IntegrationError:
        pass


def test_migration_rewrites_legacy_media_urls_to_object_keys(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "media-keys.db"
    database_url = f"sqlite+pysqlite:///{database_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    config = Config(os.environ["ALEMBIC_INI_PATH"])
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "0019_exercise_photos")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO trainer_exercises (
                    row_id, trainer_user_id, exercise_name, video_url, start_image_url
                ) VALUES (
                    'row-legacy',
                    'trainer-legacy',
                    'Legacy Squat',
                    '/api/v1/trainers/media/videos/platform/ex/demo.mp4',
                    '/api/v1/trainers/media/photos/platform/ex/start/demo.jpg'
                )
                """
            )
        )
    command.upgrade(config, "head")
    with engine.connect() as connection:
        row = connection.execute(
            text(
                """
                SELECT video_url, start_image_url, end_image_url
                FROM trainer_exercises
                WHERE row_id = 'row-legacy'
                """
            )
        ).one()
    assert row.video_url == "videos/platform/ex/demo.mp4"
    assert row.start_image_url == "photos/platform/ex/start/demo.jpg"
    assert row.end_image_url is None
