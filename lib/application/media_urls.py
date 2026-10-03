"""Подпись URL медиа для вставки в <img src> без заголовка Authorization.

Контракт: в API отдаётся относительный URL
``/api/v1/trainers/media/{object_key}?expires={unix}&signature={hex}``.
Подпись — HMAC-SHA256 от строки ``"{expires}\\n{object_key}"``.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from urllib.parse import quote

from application.errors import ForbiddenError, IntegrationError
from application.media_keys import (
    MEDIA_URL_PREFIX,
    is_internal_media_key,
    normalize_stored_media,
)


class MediaUrlSigner:
    def __init__(
        self,
        secret: str,
        ttl_seconds: int,
        *,
        photos_prefix: str = "photos/",
        videos_prefix: str = "videos/",
        media_prefix: str = MEDIA_URL_PREFIX,
    ) -> None:
        self._secret = secret
        self._ttl_seconds = max(int(ttl_seconds), 1)
        self._photos_prefix = photos_prefix
        self._videos_prefix = videos_prefix
        self._media_prefix = media_prefix

    def sign(self, stored: str | None, *, now: int | None = None) -> str | None:
        if stored is None or not str(stored).strip():
            return None
        key = normalize_stored_media(stored)
        if key is None:
            return None
        if not is_internal_media_key(key, photos_prefix=self._photos_prefix, videos_prefix=self._videos_prefix):
            # Внешняя ссылка не подписывается и отдаётся как сохранена.
            return stored.strip()
        self._require_secret()
        issued_at = int(time.time()) if now is None else int(now)
        expires = issued_at + self._ttl_seconds
        signature = self._signature(key, expires)
        encoded = quote(key, safe="/")
        return f"{self._media_prefix}{encoded}?expires={expires}&signature={signature}"

    def verify(
        self,
        object_key: str,
        expires: str | None,
        signature: str | None,
        *,
        now: int | None = None,
    ) -> int:
        """Проверить подпись и вернуть unix-время истечения."""
        self._require_secret()
        key = normalize_stored_media(object_key)
        if key is None or not expires or not signature:
            raise ForbiddenError("media url signature is missing")
        try:
            expires_at = int(expires)
        except (TypeError, ValueError) as exc:
            raise ForbiddenError("media url signature is invalid") from exc
        current = int(time.time()) if now is None else int(now)
        if expires_at < current:
            raise ForbiddenError("media url signature is expired")
        expected = self._signature(key, expires_at)
        if len(signature) != len(expected) or not hmac.compare_digest(expected, signature):
            raise ForbiddenError("media url signature is invalid")
        return expires_at

    def _require_secret(self) -> None:
        if not self._secret:
            raise IntegrationError("media url signing is not configured")

    def _signature(self, object_key: str, expires: int) -> str:
        payload = f"{expires}\n{object_key}".encode()
        return hmac.new(self._secret.encode(), payload, hashlib.sha256).hexdigest()
