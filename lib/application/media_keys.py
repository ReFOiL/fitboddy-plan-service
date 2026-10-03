"""Нормализация ключей объектов медиа и проверка владельца.

В БД хранится ключ объекта (например ``photos/platform/<row>/start/<id>.jpg``),
а не готовый URL. Старые строки могли содержать путь ``/api/v1/trainers/media/...``.
"""

from __future__ import annotations

from urllib.parse import quote, unquote

MEDIA_URL_PREFIX = "/api/v1/trainers/media/"
PLATFORM_MEDIA_OWNER = "platform"


def normalize_stored_media(value: str | None) -> str | None:
    """Привести сохранённое значение к ключу объекта или вернуть None."""
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    if text.startswith(MEDIA_URL_PREFIX):
        text = unquote(text[len(MEDIA_URL_PREFIX) :])
    text = text.split("?", 1)[0].strip().lstrip("/")
    if not text:
        return None
    return text


def media_key_variants(object_key: str) -> list[str]:
    """Варианты одного ключа: как в БД сейчас и как в старых URL-строках."""
    normalized = normalize_stored_media(object_key)
    if normalized is None:
        return []
    encoded = quote(normalized, safe="/")
    return list(
        {
            normalized,
            f"{MEDIA_URL_PREFIX}{encoded}",
            f"{MEDIA_URL_PREFIX}{normalized}",
        }
    )


def is_safe_object_key(object_key: str) -> bool:
    normalized = object_key.replace("\\", "/").lstrip("/")
    if not normalized or normalized.startswith("/"):
        return False
    return all(part not in {"", ".", ".."} for part in normalized.split("/"))


def is_internal_media_key(object_key: str, *, photos_prefix: str, videos_prefix: str) -> bool:
    if not is_safe_object_key(object_key):
        return False
    normalized = object_key.replace("\\", "/").lstrip("/")
    return normalized.startswith(photos_prefix) or normalized.startswith(videos_prefix)


def media_key_owned_by(
    object_key: str,
    owner_id: str,
    *,
    photos_prefix: str,
    videos_prefix: str,
) -> bool:
    """Ключ принадлежит владельцу, только если лежит в его префиксе."""
    if not owner_id or not is_safe_object_key(object_key):
        return False
    normalized = object_key.replace("\\", "/").lstrip("/")
    photo_root = f"{photos_prefix}{owner_id}/"
    video_root = f"{videos_prefix}{owner_id}/"
    return normalized.startswith(photo_root) or normalized.startswith(video_root)


def etag_matches(if_none_match: str | None, etag: str | None) -> bool:
    if not if_none_match or not etag:
        return False
    header = if_none_match.strip()
    if header == "*":
        return True
    expected = etag.strip()
    for part in header.split(","):
        candidate = part.strip()
        if candidate.startswith("W/"):
            candidate = candidate[2:].strip()
        if candidate == expected:
            return True
    return False
