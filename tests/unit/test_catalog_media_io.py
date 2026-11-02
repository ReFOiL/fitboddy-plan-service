"""S3 copies for catalog clone/sync stay outside the database transaction."""

from __future__ import annotations

import os
import threading
import time
from uuid import uuid4

from sqlalchemy import delete, event, select
from sqlalchemy.exc import IntegrityError

from application.commands import ApplyCatalogSyncCommand
from application.db import DatabaseManager
from application.errors import ConflictError, IntegrationError
from application.generation import build_default_generation_orchestrator
from application.media_storage import MEDIA_COPY_CONCURRENCY, MediaCopyJob, run_media_copies
from application.models import (
    PendingMediaDeleteModel,
    PlatformExerciseModel,
    PlatformExerciseMuscleModel,
    TrainerExerciseModel,
    TrainerExerciseMuscleModel,
)
from application.repositories.trainer_exercise import TrainerCloneDraft, TrainerExerciseRepository
from application.use_cases import PlanService


class _Storage:
    def __init__(self, session) -> None:
        self.session = session
        self.objects: dict[str, bytes] = {}
        self.deleted: list[str] = []
        self.copy_in_transaction: list[bool] = []
        self.fail_deletes = 0
        self.photos_prefix = "photos/"
        self.videos_prefix = "videos/"
        self._seq = 0

    def copy_owned(self, source_key: str, *, owner_id: str, row_id: str, slot: str) -> str:
        self.copy_in_transaction.append(self.session.in_transaction())
        self._seq += 1
        ext = source_key.rsplit(".", 1)[-1]
        if slot == "video":
            dest = f"videos/{owner_id}/{row_id}/copy{self._seq}.{ext}"
        else:
            dest = f"photos/{owner_id}/{row_id}/{slot}/copy{self._seq}.{ext}"
        self.objects[dest] = self.objects[source_key]
        return dest

    def delete_media_sync(self, object_name: str) -> None:
        if self.fail_deletes:
            self.fail_deletes -= 1
            raise IntegrationError(f"minio down {object_name}")
        self.deleted.append(object_name)
        self.objects.pop(object_name, None)


def _service(session, storage: _Storage) -> PlanService:
    return PlanService(
        session=session,
        generation_orchestrator=build_default_generation_orchestrator(session, media_storage=storage),
        profile_gateway=None,  # type: ignore[arg-type]
        require_profile_completion=False,
        media_storage=storage,  # type: ignore[arg-type]
    )


def _platform(
    session,
    *,
    name: str,
    start_key: str | None,
    muscles: list[tuple[str, str, int]] | None = None,
) -> PlatformExerciseModel:
    row_id = str(uuid4())
    model = PlatformExerciseModel(
        row_id=row_id,
        catalog_key=f"plan02-{row_id}",
        exercise_name=name,
        equipment="none",
        is_cardio=False,
        is_hold=False,
        difficulty=1,
        workout_category="full_body",
        default_sets=3,
        default_reps=8,
        default_rest_seconds=60,
        is_active=True,
        start_image_url=start_key,
    )
    session.add(model)
    for slug, role, position in muscles or []:
        session.add(
            PlatformExerciseMuscleModel(
                platform_exercise_id=row_id,
                muscle_slug=slug,
                role=role,
                position=position,
            )
        )
    session.commit()
    return model


def _cleanup(session, *, trainer_user_id: str, platform_ids: list[str]) -> None:
    session.rollback()
    if trainer_user_id:
        session.execute(delete(TrainerExerciseModel).where(TrainerExerciseModel.trainer_user_id == trainer_user_id))
        session.execute(delete(PendingMediaDeleteModel).where(PendingMediaDeleteModel.owner_id == trainer_user_id))
    if platform_ids:
        session.execute(delete(PlatformExerciseModel).where(PlatformExerciseModel.row_id.in_(platform_ids)))
    session.commit()


def test_sync_copies_outside_transaction_and_retries_failed_deletes() -> None:
    trainer_user_id = f"trainer-plan02-{uuid4()}"
    db = DatabaseManager(os.environ["DATABASE_URL"])
    session = db.create_session()
    platform_ids: list[str] = []
    try:
        source_key = "photos/platform/plan02/start/new.jpg"
        storage = _Storage(session)
        storage.objects[source_key] = b"new"
        storage.fail_deletes = 1
        platform = _platform(session, name=f"Plan02 Press {uuid4()}", start_key=source_key, muscles=[("chest", "primary", 0)])
        platform_ids.append(platform.row_id)
        old_key = f"photos/{trainer_user_id}/existing/start/old.jpg"
        storage.objects[old_key] = b"old"
        session.add(
            TrainerExerciseModel(
                row_id="plan02-existing",
                trainer_user_id=trainer_user_id,
                source_platform_exercise_id=platform.row_id,
                exercise_name="Custom press",
                equipment="none",
                is_cardio=False,
                difficulty=1,
                workout_category="full_body",
                is_hold=False,
                default_sets=3,
                default_reps=8,
                default_rest_seconds=60,
                is_active=True,
                start_image_url=old_key,
                synced_start_image_key="photos/platform/plan02/start/old.jpg",
            )
        )
        session.commit()

        service = _service(session, storage)
        result = service.apply_catalog_sync(
            ApplyCatalogSyncCommand(
                trainer_user_id=trainer_user_id,
                add_ids=[],
                update_ids=[platform.row_id],
                include_media=True,
            )
        )
        assert result.updated_ids == (platform.row_id,)
        assert storage.copy_in_transaction
        assert storage.copy_in_transaction == [False] * len(storage.copy_in_transaction)
        stored = session.get(TrainerExerciseModel, "plan02-existing")
        assert stored is not None
        assert stored.start_image_url != source_key
        assert stored.start_image_url is not None
        assert storage.objects[stored.start_image_url] == b"new"
        assert stored.synced_start_image_key == source_key
        assert old_key not in storage.deleted
        pending = session.get(PendingMediaDeleteModel, old_key)
        assert pending is not None
        assert pending.attempts == 1
        assert pending.owner_id == trainer_user_id

        storage.fail_deletes = 0
        service.apply_catalog_sync(
            ApplyCatalogSyncCommand(
                trainer_user_id=trainer_user_id,
                add_ids=[],
                update_ids=[],
                include_media=False,
            )
        )
        assert old_key in storage.deleted
        assert session.get(PendingMediaDeleteModel, old_key) is None
    finally:
        _cleanup(session, trainer_user_id=trainer_user_id, platform_ids=platform_ids)
        session.close()
        db.dispose()


def test_failed_clone_delete_is_queued_after_rollback() -> None:
    trainer_user_id = f"trainer-plan02-rollback-{uuid4()}"
    db = DatabaseManager(os.environ["DATABASE_URL"])
    session = db.create_session()
    platform_ids: list[str] = []
    try:
        source_key = "photos/platform/plan02/start/rollback.jpg"
        storage = _Storage(session)
        storage.objects[source_key] = b"bytes"
        storage.fail_deletes = 1
        platform = _platform(session, name=f"Plan02 Rollback {uuid4()}", start_key=source_key)
        platform_ids.append(platform.row_id)
        service = _service(session, storage)

        def _boom(_drafts: list[TrainerCloneDraft]) -> None:
            raise IntegrityError("INSERT", {}, Exception("duplicate link"))

        service._trainer_exercises.insert_clones = _boom  # type: ignore[method-assign]
        try:
            service.apply_catalog_sync(
                ApplyCatalogSyncCommand(
                    trainer_user_id=trainer_user_id,
                    add_ids=[platform.row_id],
                    update_ids=[],
                    include_media=True,
                )
            )
        except ConflictError:
            pass
        else:
            raise AssertionError("expected catalog sync conflict")

        assert storage.copy_in_transaction == [False]
        created = [key for key in storage.objects if key.startswith(f"photos/{trainer_user_id}/")]
        assert len(created) == 1
        pending = session.get(PendingMediaDeleteModel, created[0])
        assert pending is not None
        assert pending.attempts == 1
        rows = session.scalars(
            select(TrainerExerciseModel).where(TrainerExerciseModel.trainer_user_id == trainer_user_id)
        ).all()
        assert rows == []
    finally:
        _cleanup(session, trainer_user_id=trainer_user_id, platform_ids=platform_ids)
        session.close()
        db.dispose()


def test_muscle_copy_uses_one_select_and_one_insert() -> None:
    trainer_user_id = f"trainer-plan02-muscles-{uuid4()}"
    db = DatabaseManager(os.environ["DATABASE_URL"])
    session = db.create_session()
    platform_ids: list[str] = []
    statements: list[str] = []

    def _record(_conn, _cursor, statement, _parameters, _context, _executemany) -> None:
        statements.append(statement)

    event.listen(session.get_bind(), "before_cursor_execute", _record)
    try:
        first = _platform(
            session,
            name=f"Plan02 Muscle A {uuid4()}",
            start_key=None,
            muscles=[("chest", "primary", 0), ("triceps", "secondary", 0)],
        )
        second = _platform(
            session,
            name=f"Plan02 Muscle B {uuid4()}",
            start_key=None,
            muscles=[("quadriceps", "primary", 0), ("glutes", "secondary", 0)],
        )
        platform_ids.extend([first.row_id, second.row_id])
        drafts = [
            TrainerCloneDraft.from_platform(first, trainer_user_id=trainer_user_id, row_id=str(uuid4())),
            TrainerCloneDraft.from_platform(second, trainer_user_id=trainer_user_id, row_id=str(uuid4())),
        ]
        statements.clear()
        TrainerExerciseRepository(session).insert_clones(drafts)
        session.commit()

        muscle_sql = [item.lower() for item in statements if "exercise_muscle" in item.lower()]
        selects = [item for item in muscle_sql if item.lstrip().startswith("select")]
        deletes = [item for item in muscle_sql if item.lstrip().startswith("delete")]
        inserts = [item for item in muscle_sql if item.lstrip().startswith("insert")]
        assert len(selects) == 1
        assert deletes == []
        assert len(inserts) == 1
        copied = {
            (row.trainer_exercise_id, row.muscle_slug, row.role)
            for row in session.scalars(
                select(TrainerExerciseMuscleModel).where(
                    TrainerExerciseMuscleModel.trainer_exercise_id.in_([draft.row_id for draft in drafts])
                )
            ).all()
        }
        assert copied == {
            (drafts[0].row_id, "chest", "primary"),
            (drafts[0].row_id, "triceps", "secondary"),
            (drafts[1].row_id, "quadriceps", "primary"),
            (drafts[1].row_id, "glutes", "secondary"),
        }
    finally:
        event.remove(session.get_bind(), "before_cursor_execute", _record)
        _cleanup(session, trainer_user_id=trainer_user_id, platform_ids=platform_ids)
        session.close()
        db.dispose()


def test_media_copies_run_on_worker_threads() -> None:
    caller = threading.get_ident()
    seen: list[int] = []

    class _PoolStorage:
        photos_prefix = "photos/"
        videos_prefix = "videos/"

        def copy_owned(self, source_key: str, *, owner_id: str, row_id: str, slot: str) -> str:
            time.sleep(0.05)
            seen.append(threading.get_ident())
            return f"photos/{owner_id}/{row_id}/{slot}/copy.jpg"

    jobs = [
        MediaCopyJob(source="photos/platform/a/start/a.jpg", owner_id="trainer", row_id="row", slot="start"),
        MediaCopyJob(source="photos/platform/a/end/b.jpg", owner_id="trainer", row_id="row", slot="end"),
    ]
    results = run_media_copies(_PoolStorage(), jobs, max_workers=MEDIA_COPY_CONCURRENCY)  # type: ignore[arg-type]
    assert [item.created_key for item in results] == [
        "photos/trainer/row/start/copy.jpg",
        "photos/trainer/row/end/copy.jpg",
    ]
    assert len(seen) == 2
    assert all(thread_id != caller for thread_id in seen)
