from __future__ import annotations

from datetime import date
from uuid import uuid4

from sqlalchemy.orm import Session

from application.generation import GenerationOrchestrator, PlanGenerationInput, SeedCatalogProvider
from application.gateways import ProfileGateway
from application.commands import (
    AddTrainerExerciseCommand,
    ArchiveTrainerExerciseCommand,
    GeneratePlanCommand,
    GetActivePlanCommand,
    GetPlanDayCommand,
    ListClientLoadsCommand,
    ListTrainerExercisesCommand,
    UpdateTrainerExerciseCommand,
    UpsertClientLoadCommand,
)
from application.errors import PlanNotFoundError, TrainerExerciseNotFoundError, ValidationError
from application.models import PlanDayModel, PlanExerciseModel, TrainerExerciseModel, TrainingPlanModel
from application.repositories import (
    ClientExerciseLoadRepository,
    PlanDayRepository,
    PlanExerciseRepository,
    PlanMapper,
    TrainerExerciseRepository,
    TrainingPlanRepository,
)
from domain.entities import ClientExerciseLoad, PlanDay, TrainerExercise, TrainingPlan
from domain.equipment import (
    is_valid_exercise_equipment,
    normalize_equipment_list,
    normalize_equipment_name,
)
from domain.value_objects import TrainingGoal, TrainingLevel, WorkoutLocation

_ALLOWED_LOAD_SCHEMES = {"flat", "ascending", "descending", "custom"}


class PlanService:
    _ALLOWED_WORKOUT_CATEGORIES = {"upper", "lower", "core", "full_body"}

    def __init__(
        self,
        session: Session,
        *,
        generation_orchestrator: GenerationOrchestrator,
        profile_gateway: ProfileGateway,
        require_profile_completion: bool,
    ) -> None:
        self._session = session
        self._plans = TrainingPlanRepository(session)
        self._days = PlanDayRepository(session)
        self._lines = PlanExerciseRepository(session)
        self._trainer_exercises = TrainerExerciseRepository(session)
        self._client_loads = ClientExerciseLoadRepository(session)
        self._mapper = PlanMapper()
        self._generation_orchestrator = generation_orchestrator
        self._profile_gateway = profile_gateway
        self._require_profile_completion = require_profile_completion

    def generate_plan(self, command: GeneratePlanCommand) -> TrainingPlan:
        if self._require_profile_completion and not self._profile_gateway.is_questionnaire_completed(command.user_id):
            raise ValidationError("questionnaire is incomplete: fill profile before plan generation")
        goal = TrainingGoal.from_raw(command.goal)
        level = TrainingLevel.from_raw(command.level)
        workout_location = WorkoutLocation.from_raw(command.workout_location)
        workouts_per_week = self._normalize_workouts_per_week(command.workouts_per_week)
        start_date = command.start_date or self._next_monday(date.today())
        unavailable = set(normalize_equipment_list(command.unavailable_equipment))
        unavailable_keys = {item.casefold() for item in unavailable}

        load_rows = self._client_loads.list_for_client_trainer(command.user_id, command.trainer_user_id)
        client_working_weights = {
            row.exercise_row_id: float(row.working_weight_kg)
            for row in load_rows
            if row.working_weight_kg is not None and row.working_weight_kg > 0
        }

        # Ensure catalog exists, then resolve available tags from trainer catalog minus exclusions.
        self._ensure_trainer_catalog_baseline(command.trainer_user_id)
        catalog_rows = self._trainer_exercises.list_by_trainer(command.trainer_user_id)
        catalog_by_key: dict[str, str] = {}
        for row in catalog_rows:
            name = normalize_equipment_name(row.equipment or "")
            if not name:
                continue
            catalog_by_key.setdefault(name.casefold(), name)
        available_equipment = {"none"} | {
            name for key, name in catalog_by_key.items() if key not in unavailable_keys
        }

        request = PlanGenerationInput(
            trainer_user_id=command.trainer_user_id,
            goal=goal,
            level=level,
            workout_location=workout_location,
            workouts_per_week=workouts_per_week,
            available_equipment=available_equipment,
            start_date=start_date,
            recent_exercise_ids=set(),
            is_first_plan=self._plans.find_active_by_user(command.user_id) is None,
            client_working_weights=client_working_weights,
        )
        generation = self._generation_orchestrator.generate(request, match_limit=24)
        if not generation.matched_pool:
            raise ValidationError("no exercises matched profile constraints")
        sessions = generation.sessions
        if not sessions:
            raise ValidationError("failed to build workout schedule")

        self._plans.replace_active(command.user_id)
        plan_id = str(uuid4())
        plan_model = self._plans.add(
            TrainingPlanModel(
                plan_id=plan_id,
                trainer_user_id=command.trainer_user_id,
                user_id=command.user_id,
                status="active",
                goal=goal.value,
                level=level.name.lower(),
                workouts_per_week=workouts_per_week,
                start_date=min(item.scheduled_for for item in sessions),
                end_date=max(item.scheduled_for for item in sessions),
            )
        )
        day_index = 1
        for session in sorted(sessions, key=lambda item: item.scheduled_for):
            day_model = self._days.add(
                PlanDayModel(
                    day_id=str(uuid4()),
                    plan_id=plan_id,
                    day_index=day_index,
                    scheduled_for=session.scheduled_for,
                    week=session.week,
                    day_of_week=session.day_of_week,
                    volume_multiplier=session.volume_multiplier,
                )
            )
            day_index += 1
            for line in session.lines:
                self._lines.add(
                    PlanExerciseModel(
                        line_id=str(uuid4()),
                        day_id=day_model.day_id,
                        exercise_id=line.exercise.exercise_id,
                        exercise_name=line.exercise.name,
                        category=line.exercise.workout_category,
                        is_cardio=line.exercise.is_cardio,
                        sort_order=line.sort_order,
                        sets=line.sets,
                        reps=line.reps,
                        duration_seconds=line.duration_seconds,
                        rest_seconds=line.rest_seconds,
                        weight_kg=line.weight_kg,
                        set_prescriptions_json=self._mapper.dumps_set_prescriptions(line.set_prescriptions),
                    )
                )
        self._session.commit()
        return self._mapper.to_domain(plan_model)

    def get_active_plan(self, command: GetActivePlanCommand) -> TrainingPlan:
        plan = self._plans.find_active_by_user(command.user_id)
        if plan is None:
            raise PlanNotFoundError("active plan not found")
        return self._mapper.to_domain(plan)

    def get_plan_day(self, command: GetPlanDayCommand) -> PlanDay:
        plan = self._plans.find_by_id(command.plan_id)
        if plan is None:
            raise PlanNotFoundError("plan not found")
        day = self._days.find_by_plan_and_index(command.plan_id, command.day_index)
        if day is None:
            raise PlanNotFoundError("plan day not found")
        return self._mapper.day_to_domain(day)

    def list_trainer_exercises(self, command: ListTrainerExercisesCommand) -> list[TrainerExercise]:
        self._ensure_trainer_catalog_baseline(command.trainer_user_id)
        rows = self._trainer_exercises.list_by_trainer(
            command.trainer_user_id,
            include_archived=command.include_archived,
        )
        return [self._mapper.trainer_exercise_to_domain(item) for item in rows]

    def list_client_loads(self, command: ListClientLoadsCommand) -> list[ClientExerciseLoad]:
        rows = self._client_loads.list_for_client_trainer(command.client_user_id, command.trainer_user_id)
        return [self._mapper.client_load_to_domain(item) for item in rows]

    def upsert_client_load(self, command: UpsertClientLoadCommand) -> ClientExerciseLoad:
        if command.working_weight_kg <= 0:
            raise ValidationError("working_weight_kg must be > 0")
        exercise = self._trainer_exercises.find_by_trainer_and_row_id(
            command.trainer_user_id,
            command.exercise_row_id,
        )
        if exercise is None or not exercise.is_active:
            raise TrainerExerciseNotFoundError("trainer exercise not found")
        model = self._client_loads.upsert(
            client_user_id=command.client_user_id,
            trainer_user_id=command.trainer_user_id,
            exercise_row_id=command.exercise_row_id,
            working_weight_kg=float(command.working_weight_kg),
        )
        self._session.commit()
        self._session.refresh(model)
        return self._mapper.client_load_to_domain(model)

    def add_trainer_exercise(self, command: AddTrainerExerciseCommand) -> TrainerExercise:
        self._validate_exercise_fields(
            command.equipment,
            command.difficulty,
            command.workout_category,
            command.is_hold,
            command.default_sets,
            command.default_reps,
            command.default_duration_seconds,
            command.default_rest_seconds,
            command.default_weight_kg,
            command.load_scheme,
            command.scheme_steps,
        )
        sets, reps, duration, rest, weight = self._normalize_baseline(
            command.is_hold,
            command.default_sets,
            command.default_reps,
            command.default_duration_seconds,
            command.default_rest_seconds,
            command.default_weight_kg,
        )
        scheme, steps = self._normalize_scheme(command.load_scheme, command.scheme_steps, command.is_hold)
        model = TrainerExerciseModel(
            row_id=str(uuid4()),
            trainer_user_id=command.trainer_user_id,
            exercise_name=command.exercise_name.strip(),
            description=(command.description.strip() if command.description and command.description.strip() else None),
            equipment=self._normalize_stored_equipment(command.equipment),
            is_cardio=command.is_cardio,
            is_hold=command.is_hold,
            difficulty=command.difficulty,
            workout_category=command.workout_category.strip().lower(),
            default_sets=sets,
            default_reps=reps,
            default_duration_seconds=duration,
            default_rest_seconds=rest,
            default_weight_kg=weight,
            load_scheme=scheme,
            scheme_steps_json=self._mapper.dumps_scheme_steps(steps),
            is_active=True,
            video_url=None,
        )
        self._trainer_exercises.add(model)
        self._session.commit()
        self._session.refresh(model)
        return self._mapper.trainer_exercise_to_domain(model)

    def update_trainer_exercise(self, command: UpdateTrainerExerciseCommand) -> TrainerExercise:
        self._validate_exercise_fields(
            command.equipment,
            command.difficulty,
            command.workout_category,
            command.is_hold,
            command.default_sets,
            command.default_reps,
            command.default_duration_seconds,
            command.default_rest_seconds,
            command.default_weight_kg,
            command.load_scheme,
            command.scheme_steps,
        )
        model = self._trainer_exercises.find_by_trainer_and_row_id(command.trainer_user_id, command.row_id)
        if model is None:
            raise TrainerExerciseNotFoundError("trainer exercise not found")
        sets, reps, duration, rest, weight = self._normalize_baseline(
            command.is_hold,
            command.default_sets,
            command.default_reps,
            command.default_duration_seconds,
            command.default_rest_seconds,
            command.default_weight_kg,
        )
        scheme, steps = self._normalize_scheme(command.load_scheme, command.scheme_steps, command.is_hold)
        model.exercise_name = command.exercise_name.strip()
        model.description = command.description.strip() if command.description and command.description.strip() else None
        model.equipment = self._normalize_stored_equipment(command.equipment)
        model.is_cardio = command.is_cardio
        model.is_hold = command.is_hold
        model.difficulty = command.difficulty
        model.workout_category = command.workout_category.strip().lower()
        model.default_sets = sets
        model.default_reps = reps
        model.default_duration_seconds = duration
        model.default_rest_seconds = rest
        model.default_weight_kg = weight
        model.load_scheme = scheme
        model.scheme_steps_json = self._mapper.dumps_scheme_steps(steps)
        if not model.is_active:
            model.is_active = True
        self._session.commit()
        self._session.refresh(model)
        return self._mapper.trainer_exercise_to_domain(model)

    def get_trainer_exercise(self, trainer_user_id: str, row_id: str) -> TrainerExercise:
        model = self._trainer_exercises.find_by_trainer_and_row_id(trainer_user_id, row_id)
        if model is None:
            raise TrainerExerciseNotFoundError("trainer exercise not found")
        return self._mapper.trainer_exercise_to_domain(model)

    def archive_trainer_exercise(self, command: ArchiveTrainerExerciseCommand) -> None:
        model = self._trainer_exercises.find_by_trainer_and_row_id(command.trainer_user_id, command.row_id)
        if model is None:
            raise TrainerExerciseNotFoundError("trainer exercise not found")
        if not model.is_active:
            return
        model.is_active = False
        self._session.commit()

    def set_trainer_exercise_video_url(
        self,
        trainer_user_id: str,
        row_id: str,
        video_url: str,
    ) -> tuple[TrainerExercise, str | None]:
        model = self._trainer_exercises.find_by_trainer_and_row_id(trainer_user_id, row_id)
        if model is None:
            raise TrainerExerciseNotFoundError("trainer exercise not found")
        previous_video_url = model.video_url
        model.video_url = video_url
        self._session.commit()
        self._session.refresh(model)
        return self._mapper.trainer_exercise_to_domain(model), previous_video_url

    def clear_trainer_exercise_video_url(self, trainer_user_id: str, row_id: str) -> tuple[TrainerExercise, str | None]:
        model = self._trainer_exercises.find_by_trainer_and_row_id(trainer_user_id, row_id)
        if model is None:
            raise TrainerExerciseNotFoundError("trainer exercise not found")
        previous_video_url = model.video_url
        model.video_url = None
        self._session.commit()
        self._session.refresh(model)
        return self._mapper.trainer_exercise_to_domain(model), previous_video_url

    @staticmethod
    def _normalize_workouts_per_week(value: int) -> int:
        if value < 1:
            raise ValidationError("workouts_per_week must be >= 1")
        return min(value, 7)

    @staticmethod
    def _next_monday(from_date: date) -> date:
        weekday = from_date.weekday()
        if weekday == 0:
            return from_date
        return from_date.fromordinal(from_date.toordinal() + (7 - weekday))

    @staticmethod
    def _validate_exercise_fields(
        equipment: str,
        difficulty: int,
        workout_category: str,
        is_hold: bool,
        default_sets: int,
        default_reps: int | None,
        default_duration_seconds: int | None,
        default_rest_seconds: int,
        default_weight_kg: float | None,
        load_scheme: str,
        scheme_steps: list[float],
    ) -> None:
        if not equipment.strip():
            raise ValidationError("equipment must not be empty")
        if not is_valid_exercise_equipment(equipment):
            raise ValidationError("equipment must be 'none' or a name (2–64 chars)")
        if difficulty < 1 or difficulty > 5:
            raise ValidationError("difficulty must be between 1 and 5")
        normalized_category = workout_category.strip().lower()
        if not normalized_category:
            raise ValidationError("workout_category must not be empty")
        if normalized_category not in PlanService._ALLOWED_WORKOUT_CATEGORIES:
            raise ValidationError("workout_category must be one of: upper, lower, core, full_body")
        if default_sets < 1 or default_sets > 10:
            raise ValidationError("default_sets must be between 1 and 10")
        if default_rest_seconds < 0 or default_rest_seconds > 600:
            raise ValidationError("default_rest_seconds must be between 0 and 600")
        if default_weight_kg is not None and default_weight_kg < 0:
            raise ValidationError("default_weight_kg must be >= 0")
        if is_hold:
            if default_duration_seconds is None or default_duration_seconds < 5 or default_duration_seconds > 3600:
                raise ValidationError("default_duration_seconds must be between 5 and 3600 for timed exercises")
        elif default_reps is None or default_reps < 1 or default_reps > 100:
            raise ValidationError("default_reps must be between 1 and 100 for rep-based exercises")
        scheme = load_scheme.strip().lower()
        if scheme not in _ALLOWED_LOAD_SCHEMES:
            raise ValidationError("load_scheme must be one of: flat, ascending, descending, custom")
        if scheme == "custom":
            if not scheme_steps:
                raise ValidationError("scheme_steps required for custom load_scheme")
            if any(step <= 0 for step in scheme_steps):
                raise ValidationError("scheme_steps must contain positive coefficients")

    @staticmethod
    def _normalize_stored_equipment(equipment: str) -> str:
        cleaned = " ".join(equipment.strip().split())
        if cleaned.casefold() == "none":
            return "none"
        normalized = normalize_equipment_name(cleaned)
        if normalized is None:
            raise ValidationError("equipment must be 'none' or a name (2–64 chars)")
        return normalized

    @staticmethod
    def _normalize_baseline(
        is_hold: bool,
        default_sets: int,
        default_reps: int | None,
        default_duration_seconds: int | None,
        default_rest_seconds: int,
        default_weight_kg: float | None,
    ) -> tuple[int, int | None, int | None, int, float | None]:
        weight = None if default_weight_kg is None else float(default_weight_kg)
        if is_hold:
            return default_sets, None, default_duration_seconds, default_rest_seconds, weight
        return default_sets, default_reps, None, default_rest_seconds, weight

    @staticmethod
    def _normalize_scheme(load_scheme: str, scheme_steps: list[float], is_hold: bool) -> tuple[str, list[float]]:
        _ = is_hold
        scheme = load_scheme.strip().lower() or "flat"
        if scheme == "custom":
            return scheme, [float(step) for step in scheme_steps if step > 0]
        return scheme, []

    def _ensure_trainer_catalog_baseline(self, trainer_user_id: str) -> None:
        existing = self._trainer_exercises.list_by_trainer(trainer_user_id, include_archived=True)
        if existing:
            return
        baseline = SeedCatalogProvider().list_exercises(
            PlanGenerationInput(
                trainer_user_id=trainer_user_id,
                goal=TrainingGoal.MAINTENANCE,
                level=TrainingLevel.INTERMEDIATE,
                workout_location=WorkoutLocation.BOTH,
                workouts_per_week=3,
                available_equipment={"none"},
                start_date=date.today(),
                recent_exercise_ids=set(),
                is_first_plan=True,
            )
        )
        self._trainer_exercises.ensure_baseline_for_trainer(trainer_user_id, baseline)
        self._session.commit()
