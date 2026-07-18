from __future__ import annotations

from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from application.generation.models import ExerciseCandidate
from application.models import PlatformExerciseModel
from application.repositories.serialization import dumps_scheme_steps


class PlatformExerciseRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_all(self, *, include_archived: bool = False) -> list[PlatformExerciseModel]:
        statement = select(PlatformExerciseModel)
        if not include_archived:
            statement = statement.where(PlatformExerciseModel.is_active.is_(True))
        statement = statement.order_by(PlatformExerciseModel.exercise_name.asc())
        return list(self._session.scalars(statement).all())

    def list_page(
        self,
        *,
        include_archived: bool = True,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[PlatformExerciseModel], int]:
        statement = select(PlatformExerciseModel)
        count_statement = select(func.count()).select_from(PlatformExerciseModel)
        if not include_archived:
            statement = statement.where(PlatformExerciseModel.is_active.is_(True))
            count_statement = count_statement.where(PlatformExerciseModel.is_active.is_(True))
        total = int(self._session.execute(count_statement).scalar_one())
        rows = list(
            self._session.scalars(
                statement.order_by(PlatformExerciseModel.updated_at.desc()).offset(offset).limit(limit)
            ).all()
        )
        return rows, total

    def find_by_row_id(self, row_id: str) -> PlatformExerciseModel | None:
        return self._session.get(PlatformExerciseModel, row_id)

    def find_by_catalog_key(self, catalog_key: str) -> PlatformExerciseModel | None:
        statement = select(PlatformExerciseModel).where(PlatformExerciseModel.catalog_key == catalog_key)
        return self._session.scalar(statement)

    def add(self, model: PlatformExerciseModel) -> PlatformExerciseModel:
        self._session.add(model)
        self._session.flush()
        return model

    def bootstrap_if_empty(self, candidates: list[ExerciseCandidate]) -> list[PlatformExerciseModel]:
        """Fill platform base catalog once when empty (dev/bootstrap only)."""
        existing = self.list_all(include_archived=True)
        if existing:
            return self.list_all(include_archived=False)
        for item in candidates:
            self._session.add(
                PlatformExerciseModel(
                    row_id=str(uuid4()),
                    catalog_key=item.exercise_id,
                    exercise_name=item.name,
                    description=None,
                    equipment=item.equipment,
                    is_cardio=item.is_cardio,
                    difficulty=item.difficulty,
                    workout_category=item.workout_category,
                    is_hold=item.is_hold,
                    default_sets=item.default_sets,
                    default_reps=item.default_reps,
                    default_duration_seconds=item.default_duration_seconds,
                    default_rest_seconds=item.default_rest_seconds,
                    default_weight_kg=item.default_weight_kg,
                    load_scheme=item.load_scheme,
                    scheme_steps_json=dumps_scheme_steps(list(item.scheme_steps)),
                    is_active=True,
                )
            )
        self._session.flush()
        return self.list_all(include_archived=False)
