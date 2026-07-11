from __future__ import annotations

from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from application.models import PlanDayModel, PlanExerciseModel, TrainerExerciseModel, TrainingPlanModel
from application.generation.models import ExerciseCandidate
from domain.entities import PlanDay, PlanExercise, TrainerExercise, TrainingPlan


class TrainingPlanRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def find_active_by_user(self, user_id: str) -> TrainingPlanModel | None:
        statement = select(TrainingPlanModel).where(
            TrainingPlanModel.user_id == user_id,
            TrainingPlanModel.status == "active",
        )
        return self._session.scalar(statement)

    def find_by_id(self, plan_id: str) -> TrainingPlanModel | None:
        return self._session.get(TrainingPlanModel, plan_id)

    def add(self, model: TrainingPlanModel) -> TrainingPlanModel:
        self._session.add(model)
        self._session.flush()
        return model

    def replace_active(self, user_id: str) -> None:
        statement = (
            select(TrainingPlanModel)
            .where(TrainingPlanModel.user_id == user_id, TrainingPlanModel.status == "active")
        )
        active = self._session.scalars(statement).all()
        for item in active:
            item.status = "archived"
        self._session.flush()

    def purge_plan_days(self, plan_id: str) -> None:
        day_ids_statement = select(PlanDayModel.day_id).where(PlanDayModel.plan_id == plan_id)
        day_ids = list(self._session.scalars(day_ids_statement).all())
        if day_ids:
            self._session.execute(delete(PlanExerciseModel).where(PlanExerciseModel.day_id.in_(day_ids)))
        self._session.execute(delete(PlanDayModel).where(PlanDayModel.plan_id == plan_id))
        self._session.flush()


class PlanDayRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, model: PlanDayModel) -> PlanDayModel:
        self._session.add(model)
        self._session.flush()
        return model

    def find_by_plan_and_index(self, plan_id: str, day_index: int) -> PlanDayModel | None:
        statement = select(PlanDayModel).where(
            PlanDayModel.plan_id == plan_id,
            PlanDayModel.day_index == day_index,
        )
        return self._session.scalar(statement)


class PlanExerciseRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, model: PlanExerciseModel) -> PlanExerciseModel:
        self._session.add(model)
        self._session.flush()
        return model


class TrainerExerciseRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_by_trainer(self, trainer_user_id: str, *, include_archived: bool = False) -> list[TrainerExerciseModel]:
        statement = select(TrainerExerciseModel).where(TrainerExerciseModel.trainer_user_id == trainer_user_id)
        if not include_archived:
            statement = statement.where(TrainerExerciseModel.is_active.is_(True))
        statement = statement.order_by(TrainerExerciseModel.exercise_name.asc())
        return list(self._session.scalars(statement).all())

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

    def ensure_baseline_for_trainer(self, trainer_user_id: str, baseline: list[ExerciseCandidate]) -> list[TrainerExerciseModel]:
        existing = self.list_by_trainer(trainer_user_id)
        if existing:
            return existing
        for item in baseline:
            self._session.add(
                TrainerExerciseModel(
                    row_id=str(uuid4()),
                    trainer_user_id=trainer_user_id,
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
                )
            )
        self._session.flush()
        return self.list_by_trainer(trainer_user_id)


class PlanMapper:
    @staticmethod
    def to_domain(plan: TrainingPlanModel) -> TrainingPlan:
        days = sorted(plan.days, key=lambda item: item.day_index)
        return TrainingPlan(
            plan_id=plan.plan_id,
            trainer_user_id=plan.trainer_user_id,
            user_id=plan.user_id,
            status=plan.status,
            goal=plan.goal,
            level=plan.level,
            workouts_per_week=plan.workouts_per_week,
            start_date=plan.start_date,
            end_date=plan.end_date,
            created_at=plan.created_at,
            updated_at=plan.updated_at,
            days=[PlanMapper.day_to_domain(day) for day in days],
        )

    @staticmethod
    def day_to_domain(day: PlanDayModel) -> PlanDay:
        exercises = sorted(day.exercises, key=lambda item: item.sort_order)
        return PlanDay(
            day_id=day.day_id,
            day_index=day.day_index,
            scheduled_for=day.scheduled_for,
            week=day.week,
            day_of_week=day.day_of_week,
            volume_multiplier=day.volume_multiplier,
            exercises=[
                PlanExercise(
                    line_id=line.line_id,
                    exercise_id=line.exercise_id,
                    exercise_name=line.exercise_name,
                    category=line.category,
                    is_cardio=line.is_cardio,
                    sort_order=line.sort_order,
                    sets=line.sets,
                    reps=line.reps,
                    duration_seconds=line.duration_seconds,
                    rest_seconds=line.rest_seconds,
                    weight_kg=line.weight_kg,
                )
                for line in exercises
            ],
        )

    @staticmethod
    def trainer_exercise_to_domain(exercise: TrainerExerciseModel) -> TrainerExercise:
        return TrainerExercise(
            row_id=exercise.row_id,
            trainer_user_id=exercise.trainer_user_id,
            exercise_name=exercise.exercise_name,
            description=exercise.description,
            equipment=exercise.equipment,
            is_cardio=exercise.is_cardio,
            is_hold=exercise.is_hold,
            difficulty=exercise.difficulty,
            workout_category=exercise.workout_category,
            default_sets=exercise.default_sets,
            default_reps=exercise.default_reps,
            default_duration_seconds=exercise.default_duration_seconds,
            default_rest_seconds=exercise.default_rest_seconds,
            default_weight_kg=exercise.default_weight_kg,
            is_active=exercise.is_active,
            video_url=exercise.video_url,
            created_at=exercise.created_at,
            updated_at=exercise.updated_at,
        )
