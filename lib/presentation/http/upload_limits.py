"""Ограничение размера тела загрузки до того, как файл целиком окажется в RAM."""

from __future__ import annotations

import json

from fastapi import HTTPException, UploadFile, status

# Запас на multipart-границы и заголовки части, сверх лимита самого файла.
MULTIPART_OVERHEAD_BYTES = 64 * 1024
_READ_CHUNK_BYTES = 64 * 1024


def upload_kind(path: str) -> str | None:
    if "/photos/" in path:
        return "photo"
    trimmed = path.rstrip("/")
    if trimmed.endswith("/video") and ("/exercises/" in path or "/platform-exercises/" in path):
        return "video"
    return None


async def read_upload_limited(upload: UploadFile, max_bytes: int) -> bytes:
    """Читать файл кусками и ответить 413, как только суммарный размер превышен."""
    chunks: list[bytes] = []
    total = 0
    try:
        while True:
            chunk = await upload.read(_READ_CHUNK_BYTES)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="upload is too large")
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        await upload.close()


def too_large_body() -> bytes:
    return json.dumps({"detail": "upload is too large"}).encode()
