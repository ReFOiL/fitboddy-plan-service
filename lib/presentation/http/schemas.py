from datetime import date, datetime
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

WorkoutCategory = Literal["upper", "lower", "core", "full_body"]
LoadScheme = Literal["flat", "ascending", "descending", "custom"]
PlanSource = Literal["trainer", "system"]


class HealthResponse(BaseModel):
    status: str


class GeneratePlanRequest(BaseModel):
    source: PlanSource = "trainer"
    trainer_user_id: str | None = Field(default=None, min_length=1, max_length=64)
    user_id: str = Field(min_length=1, max_length=64)
    goal: str = Field(min_length=2, max_length=32, default="maintenance")
    level: str = Field(min_length=2, max_length=32, default="intermediate")
    workout_location: str = Field(min_length=2, max_length=16, default="both")
    workouts_per_week: int = Field(default=3, ge=1, le=7)
    unavailable_equipment: list[str] = Field(default_factory=list)
    start_date: date | None = None

    @model_validator(mode="after")
    def validate_source_binding(self) -> Self:
        if self.source == "trainer" and not self.trainer_user_id:
            raise ValueError("trainer_user_id is required when source=trainer")
        if self.source == "system" and self.trainer_user_id:
            raise ValueError("trainer_user_id must be omitted when source=system")
        return self


class UpsertTrainerExerciseRequest(BaseModel):
    exercise_name: str = Field(min_length=2, max_length=128)
    description: str | None = Field(default=None, max_length=4000)
    equipment: str = Field(min_length=2, max_length=64, default="none")
    is_cardio: bool = False
    is_hold: bool = False
    difficulty: int = Field(default=1, ge=1, le=5)
    workout_category: WorkoutCategory = "full_body"
    default_sets: int = Field(default=3, ge=1, le=10)
    default_reps: int | None = Field(default=10, ge=1, le=100)
    default_duration_seconds: int | None = Field(default=None, ge=5, le=3600)
    default_rest_seconds: int = Field(default=60, ge=0, le=600)
    default_weight_kg: float | None = Field(default=None, ge=0)
    load_scheme: LoadScheme = "flat"
    scheme_steps: list[float] = Field(default_factory=list)
    primary_muscles: list[str] = Field(default_factory=list)
    secondary_muscles: list[str] = Field(default_factory=list)


class UpsertPlatformExerciseRequest(BaseModel):
    exercise_name: str = Field(min_length=2, max_length=128)
    description: str | None = Field(default=None, max_length=4000)
    equipment: str = Field(min_length=2, max_length=64, default="none")
    is_cardio: bool = False
    is_hold: bool = False
    difficulty: int = Field(default=1, ge=1, le=5)
    workout_category: WorkoutCategory = "full_body"
    default_sets: int = Field(default=3, ge=1, le=10)
    default_reps: int | None = Field(default=10, ge=1, le=100)
    default_duration_seconds: int | None = Field(default=None, ge=5, le=3600)
    default_rest_seconds: int = Field(default=60, ge=0, le=600)
    default_weight_kg: float | None = Field(default=None, ge=0)
    load_scheme: LoadScheme = "flat"
    scheme_steps: list[float] = Field(default_factory=list)
    catalog_key: str | None = Field(default=None, max_length=64)
    primary_muscles: list[str] = Field(default_factory=list)
    secondary_muscles: list[str] = Field(default_factory=list)


class MuscleResponse(BaseModel):
    slug: str
    name_ru: str
    sort_order: int
    body_view: str
    region_key: str


class UpsertClientLoadRequest(BaseModel):
    working_weight_kg: float = Field(gt=0)


class ClientExerciseLoadResponse(BaseModel):
    load_id: str
    client_user_id: str
    exercise_scope: str = "trainer"
    trainer_user_id: str | None = None
    exercise_row_id: str
    working_weight_kg: float
    updated_at: datetime


class SetPrescriptionResponse(BaseModel):
    set_index: int
    reps: int | None = None
    duration_seconds: int | None = None
    weight_kg: float | None = None
    rest_seconds: int | None = None


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
    weight_kg: float | None = None
    set_prescriptions: list[SetPrescriptionResponse] = Field(default_factory=list)
    note: str | None = None


class PlanDayResponse(BaseModel):
    day_id: str
    day_index: int
    scheduled_for: date
    week: int
    day_of_week: int
    volume_multiplier: float
    is_completed: bool = False
    completed_at: datetime | None = None
    scheduled_time: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    exercises: list[PlanExerciseResponse]


class TodayWorkoutResponse(BaseModel):
    plan_id: str
    source: str
    trainer_user_id: str | None = None
    day_id: str
    day_index: int
    scheduled_for: date
    week: int
    day_of_week: int
    volume_multiplier: float
    is_completed: bool
    completed_at: datetime | None = None
    scheduled_time: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    exercises: list[PlanExerciseResponse]


class TrainingPlanResponse(BaseModel):
    plan_id: str
    source: str = "trainer"
    trainer_user_id: str | None = None
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
    previous_adherence: float | None = None


class CreateEmptyPlanRequest(BaseModel):
    goal: str = Field(default="maintenance", min_length=2, max_length=32)
    level: str = Field(default="intermediate", min_length=2, max_length=32)
    workouts_per_week: int = Field(default=3, ge=1, le=7)
    start_date: date | None = None
    day_count: int = Field(default=0, ge=0, le=28)


class PlanSlotWriteRequest(BaseModel):
    """Dosage for a new slot. Omitted fields copy the trainer exercise defaults."""

    exercise_id: str = Field(min_length=1, max_length=64)
    sets: int | None = Field(default=None, ge=1, le=10)
    reps: int | None = Field(default=None, ge=1, le=100)
    duration_seconds: int | None = Field(default=None, ge=5, le=3600)
    rest_seconds: int | None = Field(default=None, ge=0, le=600)
    weight_kg: float | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=500)


class ReplacePlanDayRequest(BaseModel):
    slots: list[PlanSlotWriteRequest] = Field(default_factory=list, max_length=24)


class UpdatePlanSlotRequest(BaseModel):
    """Partial dosage update. Omitted fields stay; explicit null clears weight only."""

    sets: int | None = Field(default=None, ge=1, le=10)
    reps: int | None = Field(default=None, ge=1, le=100)
    duration_seconds: int | None = Field(default=None, ge=5, le=3600)
    rest_seconds: int | None = Field(default=None, ge=0, le=600)
    weight_kg: float | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=500)


class ReorderPlanSlotsRequest(BaseModel):
    line_ids: list[str] = Field(default_factory=list, max_length=24)


_HHMM = r"^([01]\d|2[0-3]):[0-5]\d$"


class AddPlanDayRequest(BaseModel):
    """Добавить день в уже существующий план. day_of_week: понедельник = 0."""

    week: int = Field(ge=1, le=8)
    day_of_week: int = Field(ge=0, le=6)
    scheduled_time: str | None = Field(default=None, pattern=_HHMM)


class UpdatePlanDayRequest(BaseModel):
    """Плановое время суток. null сбрасывает. Поле обязательно в теле запроса."""

    scheduled_time: str | None = Field(default=None, pattern=_HHMM)


class CopyPlanDayRequest(BaseModel):
    week: int = Field(ge=1, le=8)
    day_of_week: int = Field(ge=0, le=6)
    mode: Literal["overwrite", "append"] = "overwrite"


class CopyPlanWeekRequest(BaseModel):
    target_week: int = Field(ge=1, le=8)
    mode: Literal["overwrite", "append"] = "overwrite"


class CompletePlanDayRequest(BaseModel):
    started_at: datetime | None = None


class SessionSizeBounds(BaseModel):
    min: int = Field(ge=1, le=12)
    max: int = Field(ge=1, le=12)


class GenerationPolicyResponse(BaseModel):
    excluded_pairs: list[list[str]] = Field(default_factory=list)
    default_splits: dict[str, list[str]] = Field(default_factory=dict)
    default_workouts_per_week: dict[str, int] = Field(default_factory=dict)
    exercises_per_session: dict[str, SessionSizeBounds] = Field(default_factory=dict)


class UpsertGenerationPolicyRequest(BaseModel):
    excluded_pairs: list[list[str]] = Field(default_factory=list)
    default_splits: dict[str, list[str]] = Field(default_factory=dict)
    default_workouts_per_week: dict[str, int] = Field(default_factory=dict)
    exercises_per_session: dict[str, SessionSizeBounds] = Field(default_factory=dict)


class TrainerExerciseResponse(BaseModel):
    row_id: str
    trainer_user_id: str
    exercise_name: str
    description: str | None = None
    equipment: str
    is_cardio: bool
    is_hold: bool
    difficulty: int
    workout_category: WorkoutCategory
    default_sets: int
    default_reps: int | None = None
    default_duration_seconds: int | None = None
    default_rest_seconds: int
    default_weight_kg: float | None = None
    load_scheme: LoadScheme = "flat"
    scheme_steps: list[float] = Field(default_factory=list)
    is_active: bool
    video_url: str | None = None
    start_image_url: str | None = None
    end_image_url: str | None = None
    created_at: datetime
    updated_at: datetime
    primary_muscles: list[str] = Field(default_factory=list)
    secondary_muscles: list[str] = Field(default_factory=list)


class ExerciseVideoUploadResponse(BaseModel):
    trainer_user_id: str
    row_id: str
    video_url: str


class ExercisePhotoUploadResponse(BaseModel):
    trainer_user_id: str
    row_id: str
    position: Literal["start", "end"]
    image_url: str


class PlatformExerciseVideoUploadResponse(BaseModel):
    row_id: str
    video_url: str


class PlatformExercisePhotoUploadResponse(BaseModel):
    row_id: str
    position: Literal["start", "end"]
    image_url: str


class AdminExerciseListResponse(BaseModel):
    items: list[TrainerExerciseResponse] = Field(default_factory=list)
    total: int
    page: int
    page_size: int


class PlatformExerciseResponse(BaseModel):
    row_id: str
    catalog_key: str | None = None
    exercise_name: str
    description: str | None = None
    equipment: str
    is_cardio: bool
    is_hold: bool
    difficulty: int
    workout_category: WorkoutCategory
    default_sets: int
    default_reps: int | None = None
    default_duration_seconds: int | None = None
    default_rest_seconds: int
    default_weight_kg: float | None = None
    load_scheme: LoadScheme = "flat"
    scheme_steps: list[float] = Field(default_factory=list)
    is_active: bool
    video_url: str | None = None
    start_image_url: str | None = None
    end_image_url: str | None = None
    created_at: datetime
    updated_at: datetime
    primary_muscles: list[str] = Field(default_factory=list)
    secondary_muscles: list[str] = Field(default_factory=list)


class AdminPlatformExerciseListResponse(BaseModel):
    items: list[PlatformExerciseResponse] = Field(default_factory=list)
    total: int
    page: int
    page_size: int
