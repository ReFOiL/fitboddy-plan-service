from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from domain.value_objects import TrainingGoal, TrainingLevel, WorkoutLocation


@dataclass(frozen=True)
class SetPrescription:
    set_index: int
    reps: int | None
    duration_seconds: int | None
    weight_kg: float | None
    rest_seconds: int | None


@dataclass(frozen=True)
class ExerciseCandidate:
    exercise_id: str
    name: str
    equipment: str
    is_cardio: bool
    difficulty: int
    workout_category: str
    is_hold: bool = False
    default_sets: int = 3
    default_reps: int | None = 10
    default_duration_seconds: int | None = None
    default_rest_seconds: int = 60
    default_weight_kg: float | None = None
    load_scheme: str = "flat"
    scheme_steps: tuple[float, ...] = ()


@dataclass(frozen=True)
class ExerciseLine:
    exercise: ExerciseCandidate
    sort_order: int
    sets: int | None
    reps: int | None
    duration_seconds: int | None
    rest_seconds: int | None
    weight_kg: float | None = None
    set_prescriptions: tuple[SetPrescription, ...] = ()


@dataclass(frozen=True)
class ScheduledSession:
    scheduled_for: date
    week: int
    day_of_week: int
    volume_multiplier: float
    lines: list[ExerciseLine]


@dataclass(frozen=True)
class PlanGenerationInput:
    source: str
    trainer_user_id: str | None
    goal: TrainingGoal
    level: TrainingLevel
    workout_location: WorkoutLocation | None
    workouts_per_week: int
    available_equipment: set[str]
    start_date: date
    recent_exercise_ids: set[str]
    is_first_plan: bool
    client_working_weights: dict[str, float] = field(default_factory=dict)
    adherence_score: float = 1.0
    weekly_split: tuple[str, ...] = ()
    excluded_pairs: tuple[tuple[str, str], ...] = ()
    session_size_min: int = 4
    session_size_max: int = 7
