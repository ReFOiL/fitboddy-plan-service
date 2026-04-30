from dataclasses import dataclass
from datetime import date, datetime


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


@dataclass(frozen=True)
class PlanDay:
    day_id: str
    day_index: int
    scheduled_for: date
    week: int
    day_of_week: int
    volume_multiplier: float
    exercises: list[PlanExercise]


@dataclass(frozen=True)
class TrainingPlan:
    plan_id: str
    trainer_user_id: str
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


@dataclass(frozen=True)
class TrainerExercise:
    row_id: str
    trainer_user_id: str
    exercise_id: str
    exercise_name: str
    equipment: str
    is_cardio: bool
    difficulty: int
    workout_category: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
