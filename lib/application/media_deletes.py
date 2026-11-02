"""Очередь удаления объектов медиа.

Отдельного воркера (Redis/RQ) в сервисе нет. Ключ пишется в
``pending_media_deletes`` в той же транзакции, что и смена ссылки, а повтор
удаления выполняется при следующем sync. Неудачный немедленный delete тоже
попадает в эту таблицу, а не остаётся только в логе.
"""

from __future__ import annotations

import inspect
import logging
from collections.abc import Awaitable, Iterable
from datetime import datetime, timezone

import anyio
from sqlalchemy import delete, func, insert, or_, select
from sqlalchemy.orm import Session

from application.errors import IntegrationError
from application.media_keys import media_key_owned_by, media_key_variants, normalize_stored_media
from application.models import PendingMediaDeleteModel, PlatformExerciseModel, TrainerExerciseModel

logger = logging.getLogger(__name__)

PENDING_DELETE_BATCH = 100
_ERROR_TEXT_LIMIT = 500


def release_read_transaction(session: Session) -> None:
    """Закрыть читающую транзакцию перед долгим S3.

    Commit здесь только отпускает снимок. Если в сессии есть несохранённые
    записи, бросаем ошибку: иначе commit заберёт чужую работу.
    """
    if session.new or session.dirty or session.deleted:
        raise RuntimeError("refusing to end a database transaction that has pending writes")
    session.commit()


def media_reference_count(session: Session, object_key: str) -> int:
    """Сколько строк упражнений всё ещё ссылаются на ключ (включая старый URL)."""
    variants = media_key_variants(object_key)
    if not variants:
        return 0
    total = 0
    for model in (TrainerExerciseModel, PlatformExerciseModel):
        predicate = or_(
            model.video_url.in_(variants),
            model.start_image_url.in_(variants),
            model.end_image_url.in_(variants),
        )
        total += int(session.scalar(select(func.count()).select_from(model).where(predicate)) or 0)
    return total


def enqueue_pending_media_deletes(
    session: Session,
    items: Iterable[tuple[str, str]],
    *,
    last_error: str | None = None,
) -> None:
    """Поставить ключи в очередь. Коммит остаётся вызывающему."""
    normalized = _normalize_items(items)
    if not normalized:
        return
    existing = set(
        session.scalars(
            select(PendingMediaDeleteModel.object_key).where(
                PendingMediaDeleteModel.object_key.in_([key for key, _owner in normalized])
            )
        ).all()
    )
    fresh = [
        {
            "object_key": key,
            "owner_id": owner_id,
            "attempts": 0,
            "last_error": last_error,
        }
        for key, owner_id in normalized
        if key not in existing
    ]
    if fresh:
        session.execute(insert(PendingMediaDeleteModel), fresh)


def remember_failed_media_deletes(
    session: Session,
    items: Iterable[tuple[str, str]],
    *,
    last_error: str,
) -> None:
    """Запомнить неудачный delete и сразу закоммитить очередь."""
    normalized = _normalize_items(items)
    if not normalized:
        release_read_transaction(session)
        return
    keys = [key for key, _owner in normalized]
    rows = {
        row.object_key: row
        for row in session.scalars(
            select(PendingMediaDeleteModel).where(PendingMediaDeleteModel.object_key.in_(keys))
        ).all()
    }
    fresh: list[dict[str, object]] = []
    now = _now()
    error_text = last_error[:_ERROR_TEXT_LIMIT]
    for key, owner_id in normalized:
        current = rows.get(key)
        if current is None:
            fresh.append(
                {
                    "object_key": key,
                    "owner_id": owner_id,
                    "attempts": 1,
                    "last_error": error_text,
                }
            )
            continue
        current.attempts = int(current.attempts or 0) + 1
        current.last_error = error_text
        current.updated_at = now
    if fresh:
        session.execute(insert(PendingMediaDeleteModel), fresh)
    session.commit()


def discard_copied_objects(
    session: Session,
    storage: object | None,
    keys: Iterable[str],
    *,
    owner_id: str,
) -> None:
    """Убрать объекты, скопированные до отката транзакции.

    Удачный delete ничего не пишет. Ошибка остаётся в очереди на следующий sync.
    """
    session.rollback()
    failed: list[tuple[str, str]] = []
    error_text: str | None = None
    for key in keys:
        normalized = normalize_stored_media(key)
        if normalized is None or not _key_owned(storage, normalized, owner_id):
            continue
        try:
            delete_storage_object(storage, normalized)
        except Exception as exc:
            logger.exception("failed to delete media copied during a rolled-back clone key=%s", normalized)
            failed.append((normalized, owner_id))
            error_text = _error_text(exc)
    if not failed:
        return
    try:
        remember_failed_media_deletes(session, failed, last_error=error_text or "delete failed")
    except Exception:
        logger.exception("failed to queue media deletes after a rolled-back clone")
        session.rollback()


def drain_pending_media_deletes(
    session: Session,
    storage: object | None,
    *,
    limit: int = PENDING_DELETE_BATCH,
) -> None:
    """Повторить отложенные удаления. S3 вызывается уже после commit чтения."""
    rows = list(
        session.scalars(
            select(PendingMediaDeleteModel)
            .order_by(PendingMediaDeleteModel.attempts.asc(), PendingMediaDeleteModel.created_at.asc())
            .limit(limit)
        ).all()
    )
    queued = [(row.object_key, row.owner_id) for row in rows]
    release_read_transaction(session)
    if not queued or storage is None:
        return
    for object_key, owner_id in queued:
        if not _key_owned(storage, object_key, owner_id):
            _drop_pending(session, object_key)
            continue
        if media_reference_count(session, object_key) > 0:
            _drop_pending(session, object_key)
            continue
        release_read_transaction(session)
        try:
            delete_storage_object(storage, object_key)
        except Exception as exc:
            logger.exception("failed to delete media object key=%s", object_key)
            _record_delete_failure(session, object_key, exc)
            continue
        _drop_pending(session, object_key)


def delete_storage_object(storage: object | None, object_key: str) -> None:
    if storage is None:
        raise IntegrationError("media storage is not configured")
    sync_delete = getattr(storage, "delete_media_sync", None)
    if callable(sync_delete):
        sync_delete(object_key)
        return
    async_delete = getattr(storage, "delete_media", None)
    if not callable(async_delete):
        raise IntegrationError("media storage cannot delete objects")
    result = async_delete(object_key)
    if inspect.isawaitable(result):
        anyio.run(_await_delete, result)


async def _await_delete(awaitable: Awaitable[object]) -> None:
    await awaitable


def _normalize_items(items: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    normalized: list[tuple[str, str]] = []
    seen: set[str] = set()
    for key, owner_id in items:
        object_key = normalize_stored_media(key)
        if object_key is None or object_key in seen or not owner_id:
            continue
        seen.add(object_key)
        normalized.append((object_key, owner_id))
    return normalized


def _key_owned(storage: object | None, object_key: str, owner_id: str) -> bool:
    photos_prefix = getattr(storage, "photos_prefix", "photos/") or "photos/"
    videos_prefix = getattr(storage, "videos_prefix", "videos/") or "videos/"
    return media_key_owned_by(
        object_key,
        owner_id,
        photos_prefix=photos_prefix,
        videos_prefix=videos_prefix,
    )


def _drop_pending(session: Session, object_key: str) -> None:
    session.execute(delete(PendingMediaDeleteModel).where(PendingMediaDeleteModel.object_key == object_key))
    session.commit()


def _record_delete_failure(session: Session, object_key: str, exc: Exception) -> None:
    row = session.get(PendingMediaDeleteModel, object_key)
    if row is None:
        release_read_transaction(session)
        return
    row.attempts = int(row.attempts or 0) + 1
    row.last_error = _error_text(exc)
    row.updated_at = _now()
    session.commit()


def _error_text(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"[:_ERROR_TEXT_LIMIT]


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
