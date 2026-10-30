from dataclasses import dataclass
from datetime import date, datetime


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
    start_mode: str | None = None


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
    started_at: datetime | None = None


@dataclass(frozen=True)
class ReplacePlanExerciseCommand:
    user_id: str
    day_index: int
    line_id: str


@dataclass(frozen=True)
class GetTrainerClientPlanCommand:
    client_user_id: str
    trainer_user_id: str


@dataclass(frozen=True)
class CreateEmptyPlanCommand:
    client_user_id: str
    trainer_user_id: str
    goal: str
    level: str
    workouts_per_week: int
    start_date: date | None
    day_count: int
    start_mode: str | None = None


@dataclass(frozen=True)
class PlanSlotInput:
    exercise_id: str
    sets: int | None
    sets_specified: bool
    reps: int | None
    reps_specified: bool
    duration_seconds: int | None
    duration_specified: bool
    rest_seconds: int | None
    rest_specified: bool
    weight_kg: float | None
    weight_specified: bool
    note: str | None


@dataclass(frozen=True)
class ReplacePlanDaySlotsCommand:
    client_user_id: str
    trainer_user_id: str
    day_index: int
    slots: tuple[PlanSlotInput, ...]


@dataclass(frozen=True)
class AddPlanSlotCommand:
    client_user_id: str
    trainer_user_id: str
    day_index: int
    slot: PlanSlotInput


@dataclass(frozen=True)
class UpdatePlanSlotCommand:
    client_user_id: str
    trainer_user_id: str
    day_index: int
    line_id: str
    sets: int | None
    sets_specified: bool
    reps: int | None
    reps_specified: bool
    duration_seconds: int | None
    duration_specified: bool
    rest_seconds: int | None
    rest_specified: bool
    weight_kg: float | None
    weight_specified: bool
    note: str | None
    note_specified: bool


@dataclass(frozen=True)
class DeletePlanSlotCommand:
    client_user_id: str
    trainer_user_id: str
    day_index: int
    line_id: str


@dataclass(frozen=True)
class ReorderPlanSlotsCommand:
    client_user_id: str
    trainer_user_id: str
    day_index: int
    line_ids: tuple[str, ...]


@dataclass(frozen=True)
class AddPlanDayCommand:
    client_user_id: str
    trainer_user_id: str
    week: int
    day_of_week: int
    scheduled_time: str | None


@dataclass(frozen=True)
class RemovePlanDayCommand:
    client_user_id: str
    trainer_user_id: str
    day_index: int


@dataclass(frozen=True)
class UpdatePlanDayCommand:
    client_user_id: str
    trainer_user_id: str
    day_index: int
    scheduled_time: str | None
    scheduled_time_specified: bool


@dataclass(frozen=True)
class ChangePlanDayWeekdayCommand:
    client_user_id: str
    trainer_user_id: str
    day_index: int
    day_of_week: int


@dataclass(frozen=True)
class CopyPlanDayCommand:
    client_user_id: str
    trainer_user_id: str
    day_index: int
    week: int
    day_of_week: int
    mode: str


@dataclass(frozen=True)
class CopyPlanWeekCommand:
    client_user_id: str
    trainer_user_id: str
    week: int
    target_week: int
    mode: str


@dataclass(frozen=True)
class UpdatePlanStartCommand:
    client_user_id: str
    trainer_user_id: str
    start_mode: str
    start_date: date | None


@dataclass(frozen=True)
class ListTrainerExercisesCommand:
    trainer_user_id: str
    include_archived: bool


@dataclass(frozen=True)
class PreviewCatalogSyncCommand:
    trainer_user_id: str


@dataclass(frozen=True)
class ApplyCatalogSyncCommand:
    trainer_user_id: str
    add_ids: list[str]
    update_ids: list[str]
    include_media: bool


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
    primary_muscles: list[str]
    secondary_muscles: list[str]


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
    primary_muscles: list[str]
    secondary_muscles: list[str]


@dataclass(frozen=True)
class ArchiveTrainerExerciseCommand:
    trainer_user_id: str
    row_id: str


@dataclass(frozen=True)
class RestoreTrainerExerciseCommand:
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
    primary_muscles: list[str]
    secondary_muscles: list[str]


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
    primary_muscles: list[str]
    secondary_muscles: list[str]


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
