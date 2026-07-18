from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from application.models import PlanDayModel, PlanExerciseModel, TrainingPlanModel


class TrainingPlanRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def find_active_by_user(self, user_id: str) -> TrainingPlanModel | None:
        statement = select(TrainingPlanModel).where(
            TrainingPlanModel.user_id == user_id,
            TrainingPlanModel.status == "active",
        )
        return self._session.scalar(statement)

    def exists_for_user(self, user_id: str) -> bool:
        statement = select(TrainingPlanModel.plan_id).where(TrainingPlanModel.user_id == user_id).limit(1)
        return self._session.scalar(statement) is not None

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

    def find_by_plan_and_date(self, plan_id: str, scheduled_for: date) -> PlanDayModel | None:
        statement = select(PlanDayModel).where(
            PlanDayModel.plan_id == plan_id,
            PlanDayModel.scheduled_for == scheduled_for,
        )
        return self._session.scalar(statement)


class PlanExerciseRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, model: PlanExerciseModel) -> PlanExerciseModel:
        self._session.add(model)
        self._session.flush()
        return model

    def find_by_day_and_line(self, day_id: str, line_id: str) -> PlanExerciseModel | None:
        statement = select(PlanExerciseModel).where(
            PlanExerciseModel.day_id == day_id,
            PlanExerciseModel.line_id == line_id,
        )
        return self._session.scalar(statement)
