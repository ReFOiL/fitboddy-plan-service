"""store exercise media as object keys instead of public urls

Revision ID: 0020_media_object_keys
Revises: 0019_exercise_photos
Create Date: 2026-10-03 20:10:00
"""

from __future__ import annotations

from urllib.parse import unquote

import sqlalchemy as sa
from alembic import op

revision = "0020_media_object_keys"
down_revision = "0019_exercise_photos"
branch_labels = None
depends_on = None

_MEDIA_PREFIX = "/api/v1/trainers/media/"
_COLUMNS = ("video_url", "start_image_url", "end_image_url")
_TABLES = ("trainer_exercises", "platform_exercises")


def _to_object_key(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    if text.startswith(_MEDIA_PREFIX):
        text = unquote(text[len(_MEDIA_PREFIX) :])
    text = text.split("?", 1)[0].strip().lstrip("/")
    return text or None


def _to_public_path(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    if not text or text.startswith(_MEDIA_PREFIX) or text.startswith("http://") or text.startswith("https://"):
        return text or None
    if text.startswith("photos/") or text.startswith("videos/"):
        return f"{_MEDIA_PREFIX}{text}"
    return text


def _rewrite(table: str, transform) -> None:  # noqa: ANN001
    bind = op.get_bind()
    rows = bind.execute(sa.text(f"SELECT row_id, video_url, start_image_url, end_image_url FROM {table}")).mappings()
    for row in rows:
        params: dict[str, str | None] = {"row_id": row["row_id"]}
        assignments: list[str] = []
        for column in _COLUMNS:
            updated = transform(row[column])
            if updated != row[column]:
                params[column] = updated
                assignments.append(f"{column} = :{column}")
        if not assignments:
            continue
        bind.execute(
            sa.text(f"UPDATE {table} SET {', '.join(assignments)} WHERE row_id = :row_id"),
            params,
        )


def upgrade() -> None:
    # Старые строки хранили готовый URL прокси. Оставляем только ключ объекта.
    for table in _TABLES:
        _rewrite(table, _to_object_key)


def downgrade() -> None:
    for table in _TABLES:
        _rewrite(table, _to_public_path)
