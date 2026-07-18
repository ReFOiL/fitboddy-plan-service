from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class PlanSetPrescription:
    set_index: int
    reps: int | None
    duration_seconds: int | None
    weight_kg: float | None
    rest_seconds: int | None


@dataclass(frozen=True)
class PlanExercise:
    line_id: str
    exercise_id: str
    exercise_name: str
    category: str
    is_cardio: bool
    sort_order: int
    sets: int | None
    reps: int | None
    duration_seconds: int | None
    rest_seconds: int | None
    weight_kg: float | None
    set_prescriptions: list[PlanSetPrescription]


@dataclass(frozen=True)
class PlanDay:
    day_id: str
    day_index: int
    scheduled_for: date
    week: int
    day_of_week: int
    volume_multiplier: float
    is_completed: bool
    completed_at: datetime | None
    exercises: list[PlanExercise]


@dataclass(frozen=True)
class TodayWorkout:
    plan_id: str
    source: str
    trainer_user_id: str | None
    day: PlanDay


@dataclass(frozen=True)
class TrainingPlan:
    plan_id: str
    source: str
    trainer_user_id: str | None
    user_id: str
    status: str
    goal: str
    level: str
    workouts_per_week: int
    start_date: date
    end_date: date
    created_at: datetime
    updated_at: datetime
    days: list[PlanDay]
    previous_adherence: float | None = None


@dataclass(frozen=True)
class TrainerExercise:
    row_id: str
    trainer_user_id: str
    exercise_name: str
    description: str | None
    equipment: str
    is_cardio: bool
    is_hold: bool
    difficulty: int
    workout_category: str
    default_sets: int
    default_reps: int | None
    default_duration_seconds: int | None
    default_rest_seconds: int
    default_weight_kg: float | None
    load_scheme: str
    scheme_steps: list[float]
    is_active: bool
    video_url: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class PlatformExercise:
    row_id: str
    catalog_key: str | None
    exercise_name: str
    description: str | None
    equipment: str
    is_cardio: bool
    is_hold: bool
    difficulty: int
    workout_category: str
    default_sets: int
    default_reps: int | None
    default_duration_seconds: int | None
    default_rest_seconds: int
    default_weight_kg: float | None
    load_scheme: str
    scheme_steps: list[float]
    is_active: bool
    video_url: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class ClientExerciseLoad:
    load_id: str
    client_user_id: str
    exercise_scope: str
    trainer_user_id: str | None
    exercise_row_id: str
    working_weight_kg: float
    updated_at: datetime
