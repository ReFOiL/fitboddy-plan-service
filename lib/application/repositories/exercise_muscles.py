from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from application.models import (
    MuscleModel,
    PlatformExerciseMuscleModel,
    TrainerExerciseMuscleModel,
)
from domain.entities import Muscle


class ExerciseMuscleRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_muscles(self) -> list[Muscle]:
        rows = list(self._session.scalars(select(MuscleModel).order_by(MuscleModel.sort_order.asc())).all())
        return [
            Muscle(
                slug=row.slug,
                name_ru=row.name_ru,
                sort_order=row.sort_order,
                body_view=row.body_view,
                region_key=row.region_key,
            )
            for row in rows
        ]

    def replace_platform_muscles(
        self,
        platform_exercise_id: str,
        *,
        primary: list[str],
        secondary: list[str],
    ) -> None:
        self._session.execute(
            delete(PlatformExerciseMuscleModel).where(
                PlatformExerciseMuscleModel.platform_exercise_id == platform_exercise_id
            )
        )
        for index, slug in enumerate(primary):
            self._session.add(
                PlatformExerciseMuscleModel(
                    platform_exercise_id=platform_exercise_id,
                    muscle_slug=slug,
                    role="primary",
                    position=index,
                )
            )
        for index, slug in enumerate(secondary):
            self._session.add(
                PlatformExerciseMuscleModel(
                    platform_exercise_id=platform_exercise_id,
                    muscle_slug=slug,
                    role="secondary",
                    position=index,
                )
            )
        self._session.flush()

    def replace_trainer_muscles(
        self,
        trainer_exercise_id: str,
        *,
        primary: list[str],
        secondary: list[str],
    ) -> None:
        self._session.execute(
            delete(TrainerExerciseMuscleModel).where(
                TrainerExerciseMuscleModel.trainer_exercise_id == trainer_exercise_id
            )
        )
        for index, slug in enumerate(primary):
            self._session.add(
                TrainerExerciseMuscleModel(
                    trainer_exercise_id=trainer_exercise_id,
                    muscle_slug=slug,
                    role="primary",
                    position=index,
                )
            )
        for index, slug in enumerate(secondary):
            self._session.add(
                TrainerExerciseMuscleModel(
                    trainer_exercise_id=trainer_exercise_id,
                    muscle_slug=slug,
                    role="secondary",
                    position=index,
                )
            )
        self._session.flush()

    def list_platform_muscle_slugs(self, platform_exercise_id: str) -> tuple[list[str], list[str]]:
        rows = list(
            self._session.scalars(
                select(PlatformExerciseMuscleModel)
                .where(PlatformExerciseMuscleModel.platform_exercise_id == platform_exercise_id)
                .order_by(PlatformExerciseMuscleModel.role.asc(), PlatformExerciseMuscleModel.position.asc())
            ).all()
        )
        primary = [row.muscle_slug for row in rows if row.role == "primary"]
        secondary = [row.muscle_slug for row in rows if row.role == "secondary"]
        return primary, secondary

    def copy_platform_muscles_to_trainer(
        self,
        *,
        platform_exercise_id: str,
        trainer_exercise_id: str,
    ) -> None:
        primary, secondary = self.list_platform_muscle_slugs(platform_exercise_id)
        self.replace_trainer_muscles(trainer_exercise_id, primary=primary, secondary=secondary)
