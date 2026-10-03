from __future__ import annotations

import io
import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

import anyio
from minio import Minio
from minio.commonconfig import CopySource
from minio.error import S3Error

from application.errors import (  # type: ignore[import-not-found]
    IntegrationError,
    MediaNotFoundError,
    PayloadTooLargeError,
    UnsupportedMediaTypeError,
)
from application.media_keys import is_internal_media_key, is_safe_object_key, normalize_stored_media

logger = logging.getLogger(__name__)

_PHOTO_TYPES_BY_EXTENSION: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}
_VIDEO_TYPES_BY_EXTENSION: dict[str, str] = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
}
_STREAM_CHUNK_BYTES = 64 * 1024


class MediaValidationError(ValueError):
    pass


@dataclass(slots=True)
class OpenedMedia:
    content_type: str
    etag: str | None
    content_length: int | None
    iterator: Iterator[bytes]

    def close(self) -> None:
        closer = getattr(self.iterator, "close", None)
        if callable(closer):
            closer()


def detect_image_media_type(data: bytes) -> str | None:
    """Определить jpeg/png/webp по сигнатуре, а не по расширению."""
    if len(data) >= 3 and data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if len(data) >= 8 and data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def validate_photo_bytes(filename: str, data: bytes, *, max_bytes: int) -> tuple[str, str]:
    if len(data) > max_bytes:
        raise PayloadTooLargeError("photo is too large")
    extension = Path(filename).suffix.lower()
    declared = _PHOTO_TYPES_BY_EXTENSION.get(extension)
    if declared is None:
        raise UnsupportedMediaTypeError("invalid photo format (allowed: .jpg, .jpeg, .png, .webp)")
    detected = detect_image_media_type(data)
    if detected != declared:
        raise UnsupportedMediaTypeError("photo content does not match the file extension")
    return extension, declared


def copy_or_share(
    storage: S3MediaStorage | None,
    source: str | None,
    *,
    owner_id: str,
    row_id: str,
    slot: str,
) -> str | None:
    """Скопировать объект в префикс владельца.

    Если хранилища нет или копирование не удалось, остаётся исходный ключ:
    чужой объект при этом нельзя удалять (см. проверку префикса и ссылок).
    """
    if source is None or not str(source).strip():
        return None
    key = normalize_stored_media(source)
    if key is None:
        return None
    photos_prefix = getattr(storage, "photos_prefix", "photos/")
    videos_prefix = getattr(storage, "videos_prefix", "videos/")
    if not is_internal_media_key(key, photos_prefix=photos_prefix, videos_prefix=videos_prefix):
        return source.strip()
    if storage is None:
        return key
    try:
        return storage.copy_owned(key, owner_id=owner_id, row_id=row_id, slot=slot)
    except Exception:
        logger.exception("failed to copy media on clone; keeping shared key %s", key)
        return key


@dataclass(slots=True)
class S3MediaStorage:
    endpoint: str
    access_key: str
    secret_key: str
    bucket: str
    secure: bool
    videos_prefix: str = "videos/"
    photos_prefix: str = "photos/"
    max_video_size_bytes: int = 200 * 1024 * 1024
    max_photo_size_bytes: int = 15 * 1024 * 1024
    _client: Minio = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._client = Minio(
            self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure,
        )

    async def upload_video(self, *, owner_id: str, row_id: str, filename: str, data: bytes) -> str:
        ext, content_type = self._validate_video(filename=filename, data=data)
        object_name = self._new_object_name(f"{self.videos_prefix}{owner_id}/{row_id}/", ext)
        await anyio.to_thread.run_sync(self._put_object_sync, object_name, data, content_type)
        return object_name

    async def upload_photo(
        self,
        *,
        owner_id: str,
        row_id: str,
        filename: str,
        data: bytes,
        position: str,
    ) -> str:
        ext, content_type = validate_photo_bytes(filename, data, max_bytes=self.max_photo_size_bytes)
        object_name = self._new_object_name(f"{self.photos_prefix}{owner_id}/{row_id}/{position}/", ext)
        await anyio.to_thread.run_sync(self._put_object_sync, object_name, data, content_type)
        return object_name

    def copy_owned(self, source_key: str, *, owner_id: str, row_id: str, slot: str) -> str:
        """Синхронная копия: клон каталога выполняется в синхронном use case."""
        extension = Path(source_key).suffix.lower()
        if slot == "video":
            prefix = f"{self.videos_prefix}{owner_id}/{row_id}/"
        elif slot in {"start", "end"}:
            prefix = f"{self.photos_prefix}{owner_id}/{row_id}/{slot}/"
        else:
            raise ValueError(f"unknown media slot: {slot}")
        dest_key = self._new_object_name(prefix, extension)
        self._require_allowed_key(source_key)
        self._copy_object_sync(source_key, dest_key)
        return dest_key

    async def download_media(self, object_name: str) -> tuple[bytes, str]:
        opened = await self.open_media(object_name)
        try:
            return b"".join(opened.iterator), opened.content_type
        finally:
            opened.close()

    async def open_media(self, object_name: str) -> OpenedMedia:
        response, content_type, etag, length = await anyio.to_thread.run_sync(self._open_object_sync, object_name)

        def iterator() -> Iterator[bytes]:
            try:
                while True:
                    chunk = response.read(_STREAM_CHUNK_BYTES)
                    if not chunk:
                        break
                    yield chunk
            finally:
                response.close()
                response.release_conn()

        return OpenedMedia(
            content_type=content_type,
            etag=_normalize_etag(etag),
            content_length=length,
            iterator=iterator(),
        )

    async def delete_media(self, object_name: str) -> None:
        await anyio.to_thread.run_sync(self.delete_media_sync, object_name)

    def delete_media_sync(self, object_name: str) -> None:
        self._delete_object_sync(object_name)

    def _put_object_sync(self, object_name: str, data: bytes, content_type: str) -> None:
        # Бакет создаёт инфраструктура. Ключ сервиса умеет только get/put/delete внутри photos/ и videos/.
        self._require_allowed_key(object_name)
        try:
            self._client.put_object(
                self.bucket,
                object_name,
                io.BytesIO(data),
                length=len(data),
                content_type=content_type,
            )
        except Exception as exc:  # pragma: no cover
            raise IntegrationError("failed to upload media to s3") from exc

    def _copy_object_sync(self, source_key: str, dest_key: str) -> None:
        self._require_allowed_key(source_key)
        self._require_allowed_key(dest_key)
        try:
            self._client.copy_object(self.bucket, dest_key, CopySource(self.bucket, source_key))
        except Exception as exc:
            raise IntegrationError("failed to copy media in s3") from exc

    def _open_object_sync(self, object_name: str):
        self._require_allowed_key(object_name)
        try:
            response = self._client.get_object(self.bucket, object_name)
        except S3Error as exc:
            if exc.code in {"NoSuchKey", "NoSuchObject"}:
                raise MediaNotFoundError("media not found") from exc
            raise IntegrationError("failed to download media from s3") from exc
        except Exception as exc:  # pragma: no cover
            raise IntegrationError("failed to download media from s3") from exc
        content_type = response.headers.get("Content-Type", "application/octet-stream")
        etag = response.headers.get("ETag")
        length_header = response.headers.get("Content-Length")
        length = int(length_header) if length_header and str(length_header).isdigit() else None
        return response, content_type, etag, length

    def _delete_object_sync(self, object_name: str) -> None:
        self._require_allowed_key(object_name)
        try:
            self._client.remove_object(self.bucket, object_name)
        except Exception as exc:  # pragma: no cover
            raise IntegrationError("failed to delete media from s3") from exc

    def _new_object_name(self, key_prefix: str, ext: str) -> str:
        # UUID делает коллизию нереальной, отдельный Head/List на бакет не нужен.
        object_name = f"{key_prefix}{uuid4().hex}{ext}"
        self._require_allowed_key(object_name)
        return object_name

    def _require_allowed_key(self, object_name: str) -> None:
        if not is_safe_object_key(object_name) or not is_internal_media_key(
            object_name,
            photos_prefix=self.photos_prefix,
            videos_prefix=self.videos_prefix,
        ):
            raise IntegrationError("media key is outside the allowed prefix")

    def _validate_video(self, *, filename: str, data: bytes) -> tuple[str, str]:
        if len(data) > self.max_video_size_bytes:
            raise PayloadTooLargeError("video is too large")
        ext = Path(filename).suffix.lower()
        content_type = _VIDEO_TYPES_BY_EXTENSION.get(ext)
        if content_type is None:
            raise MediaValidationError("invalid video format (allowed: .mp4, .mov)")
        return ext, content_type


def _normalize_etag(etag: str | None) -> str | None:
    if not etag:
        return None
    text = etag.strip()
    if text.startswith("W/"):
        text = text[2:].strip()
    if not text.startswith('"'):
        text = f'"{text}"'
    return text
