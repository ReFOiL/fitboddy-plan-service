"""Клон каталога платформы в каталог тренера.

Копии S3 считаются до INSERT и только после закрытия читающей транзакции.
Сама запись в БД хранит уже готовые ключи.
"""

from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

from sqlalchemy.orm import Session

from application.catalog_sync import MEDIA_SLOTS
from application.media_deletes import discard_copied_objects, release_read_transaction
from application.media_keys import normalize_stored_media
from application.media_storage import MediaCopyJob, S3MediaStorage, run_media_copies
from application.models import PlatformExerciseModel, TrainerExerciseModel
from application.repositories.trainer_exercise import TrainerCloneDraft, TrainerExerciseRepository


def clone_platform_catalog(
    session: Session,
    storage: S3MediaStorage | None,
    trainer_user_id: str,
    platform_rows: list[PlatformExerciseModel],
) -> list[TrainerExerciseModel]:
    """Один раз скопировать активный каталог платформы тренеру.

    Если у тренера уже есть строки (включая архив), новый клон не создаётся.
    """
    repo = TrainerExerciseRepository(session)
    if repo.list_by_trainer(trainer_user_id, include_archived=True):
        return repo.list_by_trainer(trainer_user_id)

    drafts: list[TrainerCloneDraft] = []
    jobs: list[MediaCopyJob] = []
    bindings: list[tuple[int, str, str]] = []
    for item in platform_rows:
        row_id = str(uuid4())
        draft_index = len(drafts)
        drafts.append(TrainerCloneDraft.from_platform(item, trainer_user_id=trainer_user_id, row_id=row_id))
        for field, synced_field, slot in MEDIA_SLOTS:
            source = getattr(item, field)
            if source is None or not str(source).strip():
                continue
            bindings.append((draft_index, field, synced_field))
            jobs.append(
                MediaCopyJob(source=str(source), owner_id=trainer_user_id, row_id=row_id, slot=slot)
            )

    # Снимок строк уже в памяти. Соединение с БД отпускаем до CopyObject.
    release_read_transaction(session)
    results = run_media_copies(storage, jobs)
    created = [result.created_key for result in results if result.created_key]
    filled = list(drafts)
    for (draft_index, field, synced_field), job, result in zip(bindings, jobs, results, strict=True):
        filled[draft_index] = replace(
            filled[draft_index],
            **{field: result.stored, synced_field: normalize_stored_media(job.source)},
        )

    try:
        repo.insert_clones(filled)
        session.commit()
    except Exception:
        discard_copied_objects(session, storage, created, owner_id=trainer_user_id)
        raise
    return repo.list_by_trainer(trainer_user_id)
