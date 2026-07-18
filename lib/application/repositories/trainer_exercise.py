from __future__ import annotations

from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from application.models import PlatformExerciseModel, TrainerExerciseModel
from application.repositories.exercise_muscles import ExerciseMuscleRepository


class TrainerExerciseRepository:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._muscles = ExerciseMuscleRepository(session)

    def list_by_trainer(self, trainer_user_id: str, *, include_archived: bool = False) -> list[TrainerExerciseModel]:
        statement = select(TrainerExerciseModel).where(TrainerExerciseModel.trainer_user_id == trainer_user_id)
        if not include_archived:
            statement = statement.where(TrainerExerciseModel.is_active.is_(True))
        statement = statement.order_by(TrainerExerciseModel.exercise_name.asc())
        return list(self._session.scalars(statement).all())

    def list_all(
        self,
        *,
        trainer_user_id: str | None = None,
        include_archived: bool = True,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[TrainerExerciseModel], int]:
        statement = select(TrainerExerciseModel)
        count_statement = select(func.count()).select_from(TrainerExerciseModel)
        if trainer_user_id:
            statement = statement.where(TrainerExerciseModel.trainer_user_id == trainer_user_id)
            count_statement = count_statement.where(TrainerExerciseModel.trainer_user_id == trainer_user_id)
        if not include_archived:
            statement = statement.where(TrainerExerciseModel.is_active.is_(True))
            count_statement = count_statement.where(TrainerExerciseModel.is_active.is_(True))
        total = int(self._session.execute(count_statement).scalar_one())
        rows = list(
            self._session.scalars(
                statement.order_by(TrainerExerciseModel.updated_at.desc()).offset(offset).limit(limit)
            ).all()
        )
        return rows, total

    def find_by_trainer_and_row_id(
        self,
        trainer_user_id: str,
        row_id: str,
    ) -> TrainerExerciseModel | None:
        statement = select(TrainerExerciseModel).where(
            TrainerExerciseModel.trainer_user_id == trainer_user_id,
            TrainerExerciseModel.row_id == row_id,
        )
        return self._session.scalar(statement)

    def add(self, model: TrainerExerciseModel) -> TrainerExerciseModel:
        self._session.add(model)
        self._session.flush()
        return model

    def clone_from_platform(
        self,
        trainer_user_id: str,
        platform_rows: list[PlatformExerciseModel],
    ) -> list[TrainerExerciseModel]:
        """Clone platform base catalog into a trainer's personal catalog (once)."""
        existing = self.list_by_trainer(trainer_user_id, include_archived=True)
        if existing:
            return self.list_by_trainer(trainer_user_id)
        for item in platform_rows:
            trainer_row_id = str(uuid4())
            self._session.add(
                TrainerExerciseModel(
                    row_id=trainer_row_id,
                    trainer_user_id=trainer_user_id,
                    exercise_name=item.exercise_name,
                    description=item.description,
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
                    load_scheme=item.load_scheme or "flat",
                    scheme_steps_json=item.scheme_steps_json,
                    video_url=item.video_url,
                    is_active=True,
                )
            )
            self._session.flush()
            self._muscles.copy_platform_muscles_to_trainer(
                platform_exercise_id=item.row_id,
                trainer_exercise_id=trainer_row_id,
            )
        self._session.flush()
        return self.list_by_trainer(trainer_user_id)
