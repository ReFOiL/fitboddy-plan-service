"""Нормализация фото упражнений перед записью в хранилище.

Клиент сам кадрирует 4:3. Здесь только защита: декодировать, повернуть по EXIF,
уменьшить длинную сторону и перекодировать без метаданных.
"""

from __future__ import annotations

import io

from PIL import Image, ImageOps, UnidentifiedImageError

from application.errors import PayloadTooLargeError, UnsupportedMediaTypeError

# Длинная сторона готового фото. Меньшие кадры не увеличиваем.
PHOTO_MAX_EDGE_PX = 1600
# Середина диапазона 75–85: заметно легче исходника, без сильной каши.
PHOTO_ENCODE_QUALITY = 82
# Заголовок с большим размером отклоняем до decode, чтобы не раздувать память.
_MAX_SOURCE_EDGE_PX = 16_000
_MAX_SOURCE_PIXELS = 64_000_000
_JPEG_BACKGROUND = (255, 255, 255)

# PNG перекодируем в JPEG: для фото положения прозрачность не нужна.
# WebP оставляем WebP, JPEG остаётся JPEG.
_OUTPUT_BY_DECLARED_TYPE: dict[str, tuple[str, str, str]] = {
    "image/jpeg": ("JPEG", ".jpg", "image/jpeg"),
    "image/png": ("JPEG", ".jpg", "image/jpeg"),
    "image/webp": ("WEBP", ".webp", "image/webp"),
}


def normalize_photo(data: bytes, declared_type: str) -> tuple[bytes, str, str]:
    """Вернуть байты, расширение и content-type уже нормализованного фото."""
    pil_format, extension, content_type = _output_plan(declared_type)
    image = _decode_image(data)
    resized = _downscale(image)
    encoded = _encode(resized, pil_format)
    return encoded, extension, content_type


def _output_plan(declared_type: str) -> tuple[str, str, str]:
    plan = _OUTPUT_BY_DECLARED_TYPE.get(declared_type)
    if plan is None:
        raise UnsupportedMediaTypeError("invalid photo format (allowed: .jpg, .jpeg, .png, .webp)")
    return plan


def _decode_image(data: bytes) -> Image.Image:
    try:
        with Image.open(io.BytesIO(data)) as image:
            _reject_huge_source(image)
            # Анимацию не храним: в бакет попадает первый кадр.
            if getattr(image, "n_frames", 1) > 1:
                image.seek(0)
            try:
                image.load()
            except Image.DecompressionBombError as exc:
                raise PayloadTooLargeError("photo dimensions are too large") from exc
            oriented = ImageOps.exif_transpose(image)
            if oriented is None:
                return image.copy()
            return oriented
    except PayloadTooLargeError:
        raise
    except UnsupportedMediaTypeError:
        raise
    except Image.DecompressionBombError as exc:
        raise PayloadTooLargeError("photo dimensions are too large") from exc
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise UnsupportedMediaTypeError("photo is corrupt or not a supported image") from exc


def _reject_huge_source(image: Image.Image) -> None:
    width, height = image.size
    if width < 1 or height < 1:
        raise UnsupportedMediaTypeError("photo is corrupt or not a supported image")
    if (
        width > _MAX_SOURCE_EDGE_PX
        or height > _MAX_SOURCE_EDGE_PX
        or width * height > _MAX_SOURCE_PIXELS
    ):
        raise PayloadTooLargeError("photo dimensions are too large")


def _downscale(image: Image.Image) -> Image.Image:
    width, height = image.size
    long_edge = max(width, height)
    if long_edge <= PHOTO_MAX_EDGE_PX:
        return image
    scale = PHOTO_MAX_EDGE_PX / long_edge
    resized = (max(1, round(width * scale)), max(1, round(height * scale)))
    return image.resize(resized, Image.Resampling.LANCZOS)


def _has_alpha(image: Image.Image) -> bool:
    if image.mode in {"RGBA", "LA", "PA"}:
        return True
    return image.mode == "P" and "transparency" in image.info


def _for_format(image: Image.Image, pil_format: str) -> Image.Image:
    if pil_format == "WEBP" and _has_alpha(image):
        return image.convert("RGBA")
    if image.mode == "RGB":
        return image
    if _has_alpha(image):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, _JPEG_BACKGROUND)
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return image.convert("RGB")


def _encode(image: Image.Image, pil_format: str) -> bytes:
    prepared = _for_format(image, pil_format)
    # Новое изображение без info: EXIF, ICC, XMP и комментарии не копируются.
    clean = Image.new(prepared.mode, prepared.size)
    clean.paste(prepared)
    buffer = io.BytesIO()
    if pil_format == "JPEG":
        clean.save(buffer, format="JPEG", quality=PHOTO_ENCODE_QUALITY, optimize=True)
    elif pil_format == "WEBP":
        clean.save(buffer, format="WEBP", quality=PHOTO_ENCODE_QUALITY, method=4)
    else:
        raise UnsupportedMediaTypeError("invalid photo format (allowed: .jpg, .jpeg, .png, .webp)")
    return buffer.getvalue()
