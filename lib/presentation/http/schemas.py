from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

WorkoutCategory = Literal["upper", "lower", "core", "full_body"]


class HealthResponse(BaseModel):
    status: str


class GeneratePlanRequest(BaseModel):
    trainer_user_id: str = Field(min_length=1, max_length=64)
    user_id: str = Field(min_length=1, max_length=64)
    goal: str = Field(min_length=2, max_length=32, default="maintenance")
    level: str = Field(min_length=2, max_length=32, default="intermediate")
    workout_location: str = Field(min_length=2, max_length=16, default="both")
    workouts_per_week: int = Field(default=3, ge=1, le=7)
    equipment: list[str] = Field(default_factory=list)
    start_date: date | None = None


class UpsertTrainerExerciseRequest(BaseModel):
    exercise_name: str = Field(min_length=2, max_length=128)
    equipment: str = Field(min_length=2, max_length=32, default="none")
    is_cardio: bool = False
    difficulty: int = Field(default=1, ge=1, le=5)
    workout_category: WorkoutCategory = "full_body"


class PlanExerciseResponse(BaseModel):
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


class PlanDayResponse(BaseModel):
    day_id: str
    day_index: int
    scheduled_for: date
    week: int
    day_of_week: int
    volume_multiplier: float
    exercises: list[PlanExerciseResponse]


class TrainingPlanResponse(BaseModel):
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
    days: list[PlanDayResponse]


class TrainerExerciseResponse(BaseModel):
    row_id: str
    trainer_user_id: str
    exercise_id: str
    exercise_name: str
    equipment: str
    is_cardio: bool
    difficulty: int
    workout_category: WorkoutCategory
    is_active: bool
    created_at: datetime
    updated_at: datetime
