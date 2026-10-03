"""ASGI-лимит тела POST-загрузок фото и видео.

Content-Length больше лимита отклоняется сразу. Если заголовка нет, тело
считается по чанкам и обрывается на границе, без накопления лишнего в памяти.
"""

from __future__ import annotations

from presentation.http.upload_limits import MULTIPART_OVERHEAD_BYTES, too_large_body, upload_kind


class RequestBodyTooLarge(Exception):
    pass


class UploadSizeLimitMiddleware:
    def __init__(self, app) -> None:  # noqa: ANN001
        self.app = app

    async def __call__(self, scope, receive, send) -> None:  # noqa: ANN001
        if scope.get("type") != "http" or scope.get("method") != "POST":
            await self.app(scope, receive, send)
            return
        path = scope.get("path") or ""
        limit = _body_limit(scope, path)
        if limit is None:
            await self.app(scope, receive, send)
            return
        content_length = _content_length(scope)
        if content_length is not None and content_length > limit:
            await _send_413(send)
            return

        received = 0

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message.get("type") == "http.request":
                chunk = message.get("body", b"") or b""
                received += len(chunk)
                if received > limit:
                    # Не отдаём лишние байты приложению и не копим их.
                    raise RequestBodyTooLarge()
            return message

        try:
            await self.app(scope, limited_receive, send)
        except RequestBodyTooLarge:
            await _send_413(send)


def _body_limit(scope, path: str) -> int | None:  # noqa: ANN001
    kind = upload_kind(path)
    if kind is None:
        return None
    app = scope.get("app")
    handler = getattr(getattr(app, "state", None), "plan_handler", None)
    runtime = getattr(handler, "_runtime", None)
    settings = getattr(runtime, "settings", None)
    if kind == "photo":
        file_limit = getattr(settings, "s3_max_photo_bytes", 15 * 1024 * 1024)
    else:
        file_limit = getattr(settings, "s3_max_video_bytes", 200 * 1024 * 1024)
    return int(file_limit) + MULTIPART_OVERHEAD_BYTES


def _content_length(scope) -> int | None:  # noqa: ANN001
    for name, value in scope.get("headers") or []:
        if name.lower() == b"content-length":
            try:
                return int(value)
            except (TypeError, ValueError):
                return None
    return None


async def _send_413(send) -> None:  # noqa: ANN001
    body = too_large_body()
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
