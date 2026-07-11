from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class GeneratePlanCommand:
    trainer_user_id: str
    user_id: str
    goal: str
    level: str
    workout_location: str
    workouts_per_week: int
    equipment: list[str]
    start_date: date | None


@dataclass(frozen=True)
class GetActivePlanCommand:
    user_id: str


@dataclass(frozen=True)
class GetPlanDayCommand:
    plan_id: str
    day_index: int


@dataclass(frozen=True)
class ListTrainerExercisesCommand:
    trainer_user_id: str
    include_archived: bool


@dataclass(frozen=True)
class AddTrainerExerciseCommand:
    trainer_user_id: str
    exercise_name: str
    description: str | None
    equipment: str
    is_cardio: bool
    difficulty: int
    workout_category: str


@dataclass(frozen=True)
class UpdateTrainerExerciseCommand:
    trainer_user_id: str
    row_id: str
    exercise_name: str
    description: str | None
    equipment: str
    is_cardio: bool
    difficulty: int
    workout_category: str


@dataclass(frozen=True)
class ArchiveTrainerExerciseCommand:
    trainer_user_id: str
    row_id: str
