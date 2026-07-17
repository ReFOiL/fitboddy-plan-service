from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from application.models import (
    ClientExerciseLoadModel,
    PlanDayModel,
    PlanExerciseModel,
    TrainerExerciseModel,
    TrainingPlanModel,
)
from application.generation.models import ExerciseCandidate
from domain.entities import (
    ClientExerciseLoad,
    PlanDay,
    PlanExercise,
    PlanSetPrescription,
    TrainerExercise,
    TrainingPlan,
)


def _parse_scheme_steps(raw: str | None) -> list[float]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    steps: list[float] = []
    for item in parsed:
        try:
            value = float(item)
        except (TypeError, ValueError):
            continue
        if value > 0:
            steps.append(value)
    return steps


def _dumps_scheme_steps(steps: list[float]) -> str | None:
    if not steps:
        return None
    return json.dumps(steps)


def _parse_set_prescriptions(raw: str | None) -> list[PlanSetPrescription]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    result: list[PlanSetPrescription] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        try:
            set_index = int(item.get("set_index", 0))
        except (TypeError, ValueError):
            continue
        if set_index < 1:
            continue
        result.append(
            PlanSetPrescription(
                set_index=set_index,
                reps=item.get("reps"),
                duration_seconds=item.get("duration_seconds"),
                weight_kg=item.get("weight_kg"),
                rest_seconds=item.get("rest_seconds"),
            )
        )
    return sorted(result, key=lambda row: row.set_index)


def _dumps_set_prescriptions(prescriptions: list[PlanSetPrescription] | tuple) -> str | None:
    if not prescriptions:
        return None
    payload = [
        {
            "set_index": item.set_index,
            "reps": item.reps,
            "duration_seconds": item.duration_seconds,
            "weight_kg": item.weight_kg,
            "rest_seconds": item.rest_seconds,
        }
        for item in prescriptions
    ]
    return json.dumps(payload)


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
        statement = select(TrainingPlanModel).where(
            TrainingPlanModel.user_id == user_id,
            TrainingPlanModel.status == "active",
        )
        active = self._session.scalars(statement).all()
        for item in active:
            item.status = "archived"
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

    def list_all(
        self,
        *,
        trainer_user_id: str | None = None,
        include_archived: bool = True,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[TrainerExerciseModel], int]:
        from sqlalchemy import func

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
                    load_scheme=item.load_scheme,
                    scheme_steps_json=_dumps_scheme_steps(list(item.scheme_steps)),
                )
            )
        self._session.flush()
        return self.list_by_trainer(trainer_user_id)


class ClientExerciseLoadRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_client_trainer(self, client_user_id: str, trainer_user_id: str) -> list[ClientExerciseLoadModel]:
        statement = select(ClientExerciseLoadModel).where(
            ClientExerciseLoadModel.client_user_id == client_user_id,
            ClientExerciseLoadModel.trainer_user_id == trainer_user_id,
        )
        return list(self._session.scalars(statement).all())

    def find(
        self,
        client_user_id: str,
        trainer_user_id: str,
        exercise_row_id: str,
    ) -> ClientExerciseLoadModel | None:
        statement = select(ClientExerciseLoadModel).where(
            ClientExerciseLoadModel.client_user_id == client_user_id,
            ClientExerciseLoadModel.trainer_user_id == trainer_user_id,
            ClientExerciseLoadModel.exercise_row_id == exercise_row_id,
        )
        return self._session.scalar(statement)

    def upsert(
        self,
        *,
        client_user_id: str,
        trainer_user_id: str,
        exercise_row_id: str,
        working_weight_kg: float,
    ) -> ClientExerciseLoadModel:
        existing = self.find(client_user_id, trainer_user_id, exercise_row_id)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if existing is None:
            model = ClientExerciseLoadModel(
                load_id=str(uuid4()),
                client_user_id=client_user_id,
                trainer_user_id=trainer_user_id,
                exercise_row_id=exercise_row_id,
                working_weight_kg=working_weight_kg,
                updated_at=now,
            )
            self._session.add(model)
            self._session.flush()
            return model
        existing.working_weight_kg = working_weight_kg
        existing.updated_at = now
        self._session.flush()
        return existing


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
                    set_prescriptions=_parse_set_prescriptions(line.set_prescriptions_json),
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
            load_scheme=exercise.load_scheme or "flat",
            scheme_steps=_parse_scheme_steps(exercise.scheme_steps_json),
            is_active=exercise.is_active,
            video_url=exercise.video_url,
            created_at=exercise.created_at,
            updated_at=exercise.updated_at,
        )

    @staticmethod
    def client_load_to_domain(model: ClientExerciseLoadModel) -> ClientExerciseLoad:
        return ClientExerciseLoad(
            load_id=model.load_id,
            client_user_id=model.client_user_id,
            trainer_user_id=model.trainer_user_id,
            exercise_row_id=model.exercise_row_id,
            working_weight_kg=model.working_weight_kg,
            updated_at=model.updated_at,
        )

    @staticmethod
    def dumps_set_prescriptions(prescriptions: list | tuple) -> str | None:
        return _dumps_set_prescriptions(prescriptions)

    @staticmethod
    def dumps_scheme_steps(steps: list[float]) -> str | None:
        return _dumps_scheme_steps(steps)
