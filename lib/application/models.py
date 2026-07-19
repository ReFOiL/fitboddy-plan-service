from __future__ import annotations

from datetime import date, datetime
from enum import Enum as PyEnum
from typing import TypeVar

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from application.db import Base
from domain.value_objects import SessionBoundSlot, TrainingGoal, TrainingLevelName, WorkoutCategory

_E = TypeVar("_E", bound=PyEnum)


def _str_enum(enum_cls: type[_E], *, name: str) -> SAEnum:
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=False,
        length=32,
        values_callable=lambda members: [member.value for member in members],
    )


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


class MuscleModel(Base):
    __tablename__ = "muscles"

    slug: Mapped[str] = mapped_column(String(64), primary_key=True)
    name_ru: Mapped[str] = mapped_column(String(128), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    body_view: Mapped[str] = mapped_column(String(8), nullable=False)
    region_key: Mapped[str] = mapped_column(String(64), nullable=False)


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

    muscle_links: Mapped[list[TrainerExerciseMuscleModel]] = relationship(  # type: ignore[name-defined]
        "TrainerExerciseMuscleModel",
        cascade="all, delete-orphan",
        lazy="selectin",
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

    muscle_links: Mapped[list[PlatformExerciseMuscleModel]] = relationship(  # type: ignore[name-defined]
        "PlatformExerciseMuscleModel",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class PlatformExerciseMuscleModel(Base):
    __tablename__ = "platform_exercise_muscles"
    __table_args__ = (PrimaryKeyConstraint("platform_exercise_id", "muscle_slug"),)

    platform_exercise_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("platform_exercises.row_id", ondelete="CASCADE"),
        nullable=False,
    )
    muscle_slug: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("muscles.slug", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class TrainerExerciseMuscleModel(Base):
    __tablename__ = "trainer_exercise_muscles"
    __table_args__ = (PrimaryKeyConstraint("trainer_exercise_id", "muscle_slug"),)

    trainer_exercise_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("trainer_exercises.row_id", ondelete="CASCADE"),
        nullable=False,
    )
    muscle_slug: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("muscles.slug", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


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


class TrainerGenerationPolicyModel(Base):
    __tablename__ = "trainer_generation_policies"

    trainer_user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    workouts_per_week: Mapped[list[TrainerPolicyWorkoutsPerWeekModel]] = relationship(  # type: ignore[name-defined]
        "TrainerPolicyWorkoutsPerWeekModel",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    session_bounds: Mapped[list[TrainerPolicySessionBoundsModel]] = relationship(  # type: ignore[name-defined]
        "TrainerPolicySessionBoundsModel",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    split_days: Mapped[list[TrainerPolicySplitDayModel]] = relationship(  # type: ignore[name-defined]
        "TrainerPolicySplitDayModel",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    excluded_pairs: Mapped[list[TrainerPolicyExcludedPairModel]] = relationship(  # type: ignore[name-defined]
        "TrainerPolicyExcludedPairModel",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class TrainerPolicyWorkoutsPerWeekModel(Base):
    __tablename__ = "trainer_policy_workouts_per_week"
    __table_args__ = (
        CheckConstraint(
            "level IN ('beginner', 'intermediate', 'advanced')",
            name="ck_trainer_wpw_level",
        ),
        CheckConstraint(
            "workouts_per_week >= 1 AND workouts_per_week <= 7",
            name="ck_trainer_wpw_range",
        ),
    )

    trainer_user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("trainer_generation_policies.trainer_user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    level: Mapped[TrainingLevelName] = mapped_column(
        _str_enum(TrainingLevelName, name="trainer_policy_level"),
        primary_key=True,
    )
    workouts_per_week: Mapped[int] = mapped_column(Integer, nullable=False)


class TrainerPolicySessionBoundsModel(Base):
    __tablename__ = "trainer_policy_session_bounds"
    __table_args__ = (
        CheckConstraint(
            "slot IN ('default', 'beginner', 'intermediate', 'advanced', 'rehabilitation')",
            name="ck_trainer_session_slot",
        ),
        CheckConstraint("min_exercises >= 1 AND min_exercises <= 12", name="ck_trainer_session_min"),
        CheckConstraint("max_exercises >= 1 AND max_exercises <= 12", name="ck_trainer_session_max"),
        CheckConstraint("max_exercises >= min_exercises", name="ck_trainer_session_order"),
    )

    trainer_user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("trainer_generation_policies.trainer_user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    slot: Mapped[SessionBoundSlot] = mapped_column(
        _str_enum(SessionBoundSlot, name="trainer_policy_session_slot"),
        primary_key=True,
    )
    min_exercises: Mapped[int] = mapped_column(Integer, nullable=False)
    max_exercises: Mapped[int] = mapped_column(Integer, nullable=False)


class TrainerPolicySplitDayModel(Base):
    __tablename__ = "trainer_policy_split_days"
    __table_args__ = (
        CheckConstraint(
            "goal IN ('maintenance', 'weight_loss', 'muscle_gain', 'endurance', 'rehabilitation')",
            name="ck_trainer_split_goal",
        ),
        CheckConstraint(
            "level IN ('beginner', 'intermediate', 'advanced')",
            name="ck_trainer_split_level",
        ),
        CheckConstraint(
            "category IN ('upper', 'lower', 'core', 'full_body')",
            name="ck_trainer_split_category",
        ),
        CheckConstraint("position >= 0", name="ck_trainer_split_position"),
    )

    trainer_user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("trainer_generation_policies.trainer_user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    goal: Mapped[TrainingGoal] = mapped_column(
        _str_enum(TrainingGoal, name="trainer_policy_goal"),
        primary_key=True,
    )
    level: Mapped[TrainingLevelName] = mapped_column(
        _str_enum(TrainingLevelName, name="trainer_policy_split_level"),
        primary_key=True,
    )
    position: Mapped[int] = mapped_column(Integer, primary_key=True)
    category: Mapped[WorkoutCategory] = mapped_column(
        _str_enum(WorkoutCategory, name="trainer_policy_category"),
        nullable=False,
    )


class TrainerPolicyExcludedPairModel(Base):
    __tablename__ = "trainer_policy_excluded_pairs"
    __table_args__ = (
        CheckConstraint("exercise_a_id < exercise_b_id", name="ck_trainer_pair_ordered"),
    )

    trainer_user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("trainer_generation_policies.trainer_user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    exercise_a_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    exercise_b_id: Mapped[str] = mapped_column(String(64), primary_key=True)


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
