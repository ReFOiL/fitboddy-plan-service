from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class GeneratePlanCommand:
    source: str
    trainer_user_id: str | None
    user_id: str
    goal: str
    level: str
    workout_location: str
    workouts_per_week: int
    unavailable_equipment: list[str]
    start_date: date | None


@dataclass(frozen=True)
class GetActivePlanCommand:
    user_id: str


@dataclass(frozen=True)
class GetPlanDayCommand:
    plan_id: str
    day_index: int


@dataclass(frozen=True)
class GetTodayWorkoutCommand:
    user_id: str


@dataclass(frozen=True)
class CompletePlanDayCommand:
    user_id: str
    day_index: int


@dataclass(frozen=True)
class ReplacePlanExerciseCommand:
    user_id: str
    day_index: int
    line_id: str


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


@dataclass(frozen=True)
class UpdateTrainerExerciseCommand:
    trainer_user_id: str
    row_id: str
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


@dataclass(frozen=True)
class ArchiveTrainerExerciseCommand:
    trainer_user_id: str
    row_id: str


@dataclass(frozen=True)
class ListPlatformExercisesCommand:
    include_archived: bool
    page: int
    page_size: int


@dataclass(frozen=True)
class AddPlatformExerciseCommand:
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
    catalog_key: str | None


@dataclass(frozen=True)
class UpdatePlatformExerciseCommand:
    row_id: str
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
    catalog_key: str | None


@dataclass(frozen=True)
class ArchivePlatformExerciseCommand:
    row_id: str


@dataclass(frozen=True)
class ListClientLoadsCommand:
    client_user_id: str
    trainer_user_id: str


@dataclass(frozen=True)
class UpsertClientLoadCommand:
    client_user_id: str
    trainer_user_id: str
    exercise_row_id: str
    working_weight_kg: float


@dataclass(frozen=True)
class ListClientPlatformLoadsCommand:
    client_user_id: str


@dataclass(frozen=True)
class UpsertClientPlatformLoadCommand:
    client_user_id: str
    exercise_row_id: str
    working_weight_kg: float
