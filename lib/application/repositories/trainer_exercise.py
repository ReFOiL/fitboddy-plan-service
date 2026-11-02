from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, insert, select
from sqlalchemy.orm import Session

from application.models import PlatformExerciseModel, TrainerExerciseModel
from application.repositories.exercise_muscles import ExerciseMuscleRepository


@dataclass(frozen=True, slots=True)
class TrainerCloneDraft:
    """Готовая строка каталога тренера. Медиа уже разрешено до INSERT."""

    row_id: str
    trainer_user_id: str
    source_platform_exercise_id: str
    exercise_name: str
    description: str | None
    equipment: str
    is_cardio: bool
    difficulty: int
    workout_category: str
    is_hold: bool
    default_sets: int
    default_reps: int | None
    default_duration_seconds: int | None
    default_rest_seconds: int
    default_weight_kg: float | None
    load_scheme: str
    scheme_steps_json: str | None
    video_url: str | None = None
    start_image_url: str | None = None
    end_image_url: str | None = None
    synced_video_key: str | None = None
    synced_start_image_key: str | None = None
    synced_end_image_key: str | None = None
    is_active: bool = True

    @classmethod
    def from_platform(
        cls,
        model: PlatformExerciseModel,
        *,
        trainer_user_id: str,
        row_id: str,
    ) -> TrainerCloneDraft:
        return cls(
            row_id=row_id,
            trainer_user_id=trainer_user_id,
            source_platform_exercise_id=model.row_id,
            exercise_name=model.exercise_name,
            description=model.description,
            equipment=model.equipment,
            is_cardio=bool(model.is_cardio),
            difficulty=int(model.difficulty),
            workout_category=model.workout_category,
            is_hold=bool(model.is_hold),
            default_sets=int(model.default_sets),
            default_reps=model.default_reps,
            default_duration_seconds=model.default_duration_seconds,
            default_rest_seconds=int(model.default_rest_seconds),
            default_weight_kg=model.default_weight_kg,
            load_scheme=model.load_scheme or "flat",
            scheme_steps_json=model.scheme_steps_json,
        )

    def insert_mapping(self) -> dict[str, object]:
        return {
            "row_id": self.row_id,
            "trainer_user_id": self.trainer_user_id,
            "source_platform_exercise_id": self.source_platform_exercise_id,
            "exercise_name": self.exercise_name,
            "description": self.description,
            "equipment": self.equipment,
            "is_cardio": self.is_cardio,
            "difficulty": self.difficulty,
            "workout_category": self.workout_category,
            "is_hold": self.is_hold,
            "default_sets": self.default_sets,
            "default_reps": self.default_reps,
            "default_duration_seconds": self.default_duration_seconds,
            "default_rest_seconds": self.default_rest_seconds,
            "default_weight_kg": self.default_weight_kg,
            "load_scheme": self.load_scheme,
            "scheme_steps_json": self.scheme_steps_json,
            "video_url": self.video_url,
            "start_image_url": self.start_image_url,
            "end_image_url": self.end_image_url,
            "synced_video_key": self.synced_video_key,
            "synced_start_image_key": self.synced_start_image_key,
            "synced_end_image_key": self.synced_end_image_key,
            "is_active": self.is_active,
        }


class TrainerExerciseRepository:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._muscles = ExerciseMuscleRepository(session)

    @property
    def session(self) -> Session:
        return self._session

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

    def lock_for_media_update(self, trainer_user_id: str, row_id: str) -> TrainerExerciseModel | None:
        # Блокируем строку на время смены ключа, чтобы параллельные загрузки не теряли объект.
        statement = select(TrainerExerciseModel).where(
            TrainerExerciseModel.trainer_user_id == trainer_user_id,
            TrainerExerciseModel.row_id == row_id,
        )
        if self._session.get_bind().dialect.name == "postgresql":
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def add(self, model: TrainerExerciseModel) -> TrainerExerciseModel:
        self._session.add(model)
        self._session.flush()
        return model

    def insert_clones(self, drafts: list[TrainerCloneDraft]) -> None:
        """Вставить клоны одним INSERT и скопировать мышцы одним SELECT/INSERT.

        Ключи медиа уже должны быть посчитаны: этот метод не ходит в хранилище.
        """
        if not drafts:
            return
        self._session.execute(insert(TrainerExerciseModel), [draft.insert_mapping() for draft in drafts])
        self._muscles.copy_platform_muscles_bulk(
            [
                (draft.source_platform_exercise_id, draft.row_id)
                for draft in drafts
                if draft.source_platform_exercise_id
            ]
        )
