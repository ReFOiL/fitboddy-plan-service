from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from application.db import Base


class TrainingPlanModel(Base):
    __tablename__ = "training_plans"

    plan_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="trainer", index=True)
    trainer_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    goal: Mapped[str] = mapped_column(String(32), nullable=False)
    level: Mapped[str] = mapped_column(String(32), nullable=False)
    workouts_per_week: Mapped[int] = mapped_column(Integer, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    days: Mapped[list[PlanDayModel]] = relationship(  # type: ignore[name-defined]
        "PlanDayModel",
        back_populates="plan",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class PlanDayModel(Base):
    __tablename__ = "plan_days"

    day_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    plan_id: Mapped[str] = mapped_column(String(36), ForeignKey("training_plans.plan_id", ondelete="CASCADE"), index=True)
    day_index: Mapped[int] = mapped_column(Integer, nullable=False)
    scheduled_for: Mapped[date] = mapped_column(Date, nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    volume_multiplier: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    is_completed: Mapped[bool] = mapped_column(nullable=False, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    plan: Mapped[TrainingPlanModel] = relationship("TrainingPlanModel", back_populates="days")
    exercises: Mapped[list[PlanExerciseModel]] = relationship(  # type: ignore[name-defined]
        "PlanExerciseModel",
        back_populates="day",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class PlanExerciseModel(Base):
    __tablename__ = "plan_exercises"

    line_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    day_id: Mapped[str] = mapped_column(String(36), ForeignKey("plan_days.day_id", ondelete="CASCADE"), index=True)
    exercise_id: Mapped[str] = mapped_column(String(64), nullable=False)
    exercise_name: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    is_cardio: Mapped[bool] = mapped_column(nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    sets: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rest_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    set_prescriptions_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    day: Mapped[PlanDayModel] = relationship("PlanDayModel", back_populates="exercises")


class TrainerExerciseModel(Base):
    __tablename__ = "trainer_exercises"

    row_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    trainer_user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    exercise_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    equipment: Mapped[str] = mapped_column(String(32), nullable=False, default="none")
    is_cardio: Mapped[bool] = mapped_column(nullable=False, default=False)
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    workout_category: Mapped[str] = mapped_column(String(50), nullable=False, default="full_body")
    is_hold: Mapped[bool] = mapped_column(nullable=False, default=False)
    default_sets: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    default_reps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    default_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    default_rest_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    default_weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    load_scheme: Mapped[str] = mapped_column(String(32), nullable=False, default="flat")
    scheme_steps_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    video_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class PlatformExerciseModel(Base):
    __tablename__ = "platform_exercises"
    __table_args__ = (UniqueConstraint("catalog_key", name="uq_platform_exercises_catalog_key"),)

    row_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    catalog_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    exercise_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    equipment: Mapped[str] = mapped_column(String(32), nullable=False, default="none")
    is_cardio: Mapped[bool] = mapped_column(nullable=False, default=False)
    is_hold: Mapped[bool] = mapped_column(nullable=False, default=False)
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    workout_category: Mapped[str] = mapped_column(String(50), nullable=False, default="full_body")
    default_sets: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    default_reps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    default_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    default_rest_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    default_weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    load_scheme: Mapped[str] = mapped_column(String(32), nullable=False, default="flat")
    scheme_steps_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    video_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class GenerationPolicyModel(Base):
    __tablename__ = "generation_policies"

    policy_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    config_json: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ClientExerciseLoadModel(Base):
    __tablename__ = "client_exercise_loads"
    __table_args__ = (
        Index(
            "uq_client_trainer_exercise_load",
            "client_user_id",
            "trainer_user_id",
            "exercise_row_id",
            unique=True,
            sqlite_where=text("exercise_scope = 'trainer'"),
            postgresql_where=text("exercise_scope = 'trainer'"),
        ),
        Index(
            "uq_client_platform_exercise_load",
            "client_user_id",
            "exercise_row_id",
            unique=True,
            sqlite_where=text("exercise_scope = 'platform'"),
            postgresql_where=text("exercise_scope = 'platform'"),
        ),
    )

    load_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    client_user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    exercise_scope: Mapped[str] = mapped_column(String(16), nullable=False, default="trainer", index=True)
    trainer_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    exercise_row_id: Mapped[str] = mapped_column(String(36), nullable=False)
    working_weight_kg: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
