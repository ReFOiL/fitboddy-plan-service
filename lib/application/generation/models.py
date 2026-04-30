from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from domain.value_objects import EquipmentName, TrainingGoal, TrainingLevel, WorkoutLocation


@dataclass(frozen=True)
class ExerciseCandidate:
    exercise_id: str
    name: str
    equipment: str
    is_cardio: bool
    difficulty: int
    workout_category: str


@dataclass(frozen=True)
class ExerciseLine:
    exercise: ExerciseCandidate
    sort_order: int
    sets: int | None
    reps: int | None
    duration_seconds: int | None
    rest_seconds: int | None


@dataclass(frozen=True)
class ScheduledSession:
    scheduled_for: date
    week: int
    day_of_week: int
    volume_multiplier: float
    lines: list[ExerciseLine]


@dataclass(frozen=True)
class PlanGenerationInput:
    trainer_user_id: str
    goal: TrainingGoal
    level: TrainingLevel
    workout_location: WorkoutLocation | None
    workouts_per_week: int
    equipment: set[EquipmentName]
    start_date: date
    recent_exercise_ids: set[str]
    is_first_plan: bool
