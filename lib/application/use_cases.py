from __future__ import annotations

import logging
from dataclasses import replace
from datetime import date, datetime, time, timedelta, timezone
from uuid import uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from application.generation import GenerationOrchestrator, PlanGenerationInput, SeedCatalogProvider
from application.generation.policy import GenerationPolicyConfig
from application.gateways import ProfileGateway
from application.commands import (
    AddPlatformExerciseCommand,
    AddTrainerExerciseCommand,
    ArchivePlatformExerciseCommand,
    ArchiveTrainerExerciseCommand,
    RestoreTrainerExerciseCommand,
    AddPlanDayCommand,
    AddPlanSlotCommand,
    CompletePlanDayCommand,
    CopyPlanDayCommand,
    CopyPlanWeekCommand,
    CreateEmptyPlanCommand,
    DeletePlanSlotCommand,
    GeneratePlanCommand,
    GetActivePlanCommand,
    GetPlanDayCommand,
    GetTodayWorkoutCommand,
    GetTrainerClientPlanCommand,
    ListClientLoadsCommand,
    ListClientPlatformLoadsCommand,
    ListPlatformExercisesCommand,
    ListTrainerExercisesCommand,
    PlanSlotInput,
    RemovePlanDayCommand,
    ReorderPlanSlotsCommand,
    ReplacePlanDaySlotsCommand,
    ReplacePlanExerciseCommand,
    UpdatePlanDayCommand,
    UpdatePlanSlotCommand,
    UpdatePlatformExerciseCommand,
    UpdateTrainerExerciseCommand,
    UpsertClientLoadCommand,
    UpsertClientPlatformLoadCommand,
)
from application.errors import (
    ConflictError,
    PlanNotFoundError,
    PlatformExerciseNotFoundError,
    TrainerExerciseNotFoundError,
    ValidationError,
)
from application.media_keys import media_key_variants, normalize_stored_media
from application.notifications.repository import NotificationRepository
from application.media_storage import S3MediaStorage, copy_or_share
from application.models import (
    PlanDayModel,
    PlanExerciseModel,
    PlatformExerciseModel,
    TrainerExerciseModel,
    TrainingPlanModel,
)
from application.muscle_catalog import derive_workout_category, is_known_muscle_slug
from application.repositories import (
    ClientExerciseLoadRepository,
    GenerationPolicyRepository,
    PlanDayRepository,
    PlanExerciseRepository,
    PlanMapper,
    PlatformExerciseRepository,
    TrainerExerciseRepository,
    TrainerGenerationPolicyRepository,
    TrainingPlanRepository,
)
from application.repositories.exercise_muscles import ExerciseMuscleRepository
from application.repositories.serialization import dumps_set_prescriptions, parse_scheme_steps, parse_set_prescriptions
from application.weight_prescription import build_prescriptions, rescale_plan_line_weights
from domain.entities import (
    ClientExerciseLoad,
    Muscle,
    PlanDay,
    PlatformExercise,
    TodayWorkout,
    TrainerExercise,
    TrainingPlan,
)
from domain.equipment import (
    is_valid_exercise_equipment,
    normalize_equipment_list,
    normalize_equipment_name,
)
from domain.value_objects import TrainingGoal, TrainingLevel, WorkoutLocation

_ALLOWED_LOAD_SCHEMES = {"flat", "ascending", "descending", "custom"}
logger = logging.getLogger(__name__)


class PlanService:
    _ALLOWED_WORKOUT_CATEGORIES = {"upper", "lower", "core", "full_body"}
    _MAX_DAY_SLOTS = 24
    _MAX_PLAN_DAYS = 28
    _MAX_WEEK = 8
    _MAX_NOTE_LENGTH = 500

    def __init__(
        self,
        session: Session,
        *,
        generation_orchestrator: GenerationOrchestrator,
        profile_gateway: ProfileGateway,
        require_profile_completion: bool,
        media_storage: S3MediaStorage | None = None,
        plan_notice_debounce_seconds: int = 900,
    ) -> None:
        self._session = session
        self._plans = TrainingPlanRepository(session)
        self._days = PlanDayRepository(session)
        self._lines = PlanExerciseRepository(session)
        self._trainer_exercises = TrainerExerciseRepository(session)
        self._platform_exercises = PlatformExerciseRepository(session)
        self._client_loads = ClientExerciseLoadRepository(session)
        self._policies = GenerationPolicyRepository(session)
        self._trainer_policies = TrainerGenerationPolicyRepository(session)
        self._exercise_muscles = ExerciseMuscleRepository(session)
        self._mapper = PlanMapper()
        self._generation_orchestrator = generation_orchestrator
        self._profile_gateway = profile_gateway
        self._require_profile_completion = require_profile_completion
        self._media_storage = media_storage
        self._plan_notices = NotificationRepository(session)
        self._plan_notice_debounce_seconds = plan_notice_debounce_seconds

    def list_muscles(self) -> list[Muscle]:
        return self._exercise_muscles.list_muscles()

    def _normalize_muscle_lists(
        self,
        primary_muscles: list[str],
        secondary_muscles: list[str],
    ) -> tuple[list[str], list[str]]:
        primary: list[str] = []
        seen: set[str] = set()
        for raw in primary_muscles:
            slug = raw.strip().lower()
            if not slug or slug in seen:
                continue
            if not is_known_muscle_slug(slug):
                raise ValidationError(f"unknown muscle slug: {slug}")
            seen.add(slug)
            primary.append(slug)
        secondary: list[str] = []
        for raw in secondary_muscles:
            slug = raw.strip().lower()
            if not slug or slug in seen:
                continue
            if not is_known_muscle_slug(slug):
                raise ValidationError(f"unknown muscle slug: {slug}")
            seen.add(slug)
            secondary.append(slug)
        return primary, secondary

    def generate_plan(self, command: GeneratePlanCommand) -> TrainingPlan:
        if self._require_profile_completion and not self._profile_gateway.is_questionnaire_completed(command.user_id):
            raise ValidationError("questionnaire is incomplete: fill profile before plan generation")
        source = command.source.strip().lower()
        if source not in {"trainer", "system"}:
            raise ValidationError("source must be one of: trainer, system")
        if source == "trainer" and not command.trainer_user_id:
            raise ValidationError("trainer_user_id is required when source=trainer")
        if source == "system" and command.trainer_user_id:
            raise ValidationError("trainer_user_id must be omitted when source=system")

        goal = TrainingGoal.from_raw(command.goal)
        level = TrainingLevel.from_raw(command.level)
        workout_location = WorkoutLocation.from_raw(command.workout_location)
        if source == "trainer":
            assert command.trainer_user_id is not None
            policy = self._trainer_policies.get_config(command.trainer_user_id)
        else:
            policy = self._policies.get_config()
        previous_plan = self._plans.find_active_by_user(command.user_id)
        is_first_plan = not self._plans.exists_for_user(command.user_id)
        previous_adherence, recent_exercise_ids = self._adherence_from_plan(previous_plan)

        level_key = level.name.lower()
        policy_wpw = policy.workouts_per_week_for(level_key)
        base_wpw = policy_wpw if policy_wpw is not None else command.workouts_per_week
        workouts_per_week = self._normalize_workouts_per_week(
            self._adjust_wpw_by_adherence(base_wpw, previous_adherence, is_first_plan)
        )

        # Replace/rebuild always starts today (unless caller sets an explicit date).
        # Do not wait for previous plan end_date — that pushed first workouts weeks ahead
        # when the old cycle itself started in the future.
        start_date = command.start_date if command.start_date is not None else date.today()

        unavailable = set(normalize_equipment_list(command.unavailable_equipment))
        unavailable_keys = {item.casefold() for item in unavailable}

        client_working_weights: dict[str, float] = {}
        if source == "trainer":
            assert command.trainer_user_id is not None
            self._ensure_trainer_catalog_baseline(command.trainer_user_id)
            equipment_values = [
                row.equipment for row in self._trainer_exercises.list_by_trainer(command.trainer_user_id)
            ]
            load_rows = self._client_loads.list_for_client_trainer(command.user_id, command.trainer_user_id)
            client_working_weights = {
                row.exercise_row_id: float(row.working_weight_kg)
                for row in load_rows
                if row.working_weight_kg is not None and row.working_weight_kg > 0
            }
        else:
            equipment_values = [row.equipment for row in self._ensure_platform_catalog_baseline()]
            load_rows = self._client_loads.list_for_client_platform(command.user_id)
            client_working_weights = {
                row.exercise_row_id: float(row.working_weight_kg)
                for row in load_rows
                if row.working_weight_kg is not None and row.working_weight_kg > 0
            }

        available_equipment = self._available_equipment_from_catalog(equipment_values, unavailable_keys)
        weekly_split = policy.split_for(goal=goal.value, level=level_key)
        session_min, session_max = policy.session_bounds_for(
            level=level_key,
            goal=goal.value,
            is_first_plan=is_first_plan,
        )

        request = PlanGenerationInput(
            source=source,
            trainer_user_id=command.trainer_user_id,
            goal=goal,
            level=level,
            workout_location=workout_location,
            workouts_per_week=workouts_per_week,
            available_equipment=available_equipment,
            start_date=start_date,
            recent_exercise_ids=recent_exercise_ids,
            is_first_plan=is_first_plan,
            client_working_weights=client_working_weights,
            adherence_score=previous_adherence,
            weekly_split=weekly_split,
            excluded_pairs=policy.excluded_pairs,
            session_size_min=session_min,
            session_size_max=session_max,
        )
        generation = self._generation_orchestrator.generate(request, match_limit=24)
        if not generation.matched_pool:
            raise ValidationError("no exercises matched profile constraints")
        sessions = generation.sessions
        if not sessions:
            raise ValidationError("failed to build workout schedule")

        try:
            # Generate is a draft fill: the previous active plan is archived, including
            # any manual slot edits. Those edits are not copied onto the new plan.
            self._plans.replace_active(command.user_id)
            plan_id = str(uuid4())
            plan_model = self._plans.add(
                TrainingPlanModel(
                    plan_id=plan_id,
                    source=source,
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
            self._note_trainer_plan_change(plan_model, created=True)
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError("user already has an active plan") from exc
        plan = self._mapper.to_domain(plan_model)
        return replace(
            plan,
            previous_adherence=None if previous_plan is None else previous_adherence,
        )

    def get_generation_policy(self) -> GenerationPolicyConfig:
        return self._policies.get_config()

    def upsert_generation_policy(self, config: GenerationPolicyConfig) -> GenerationPolicyConfig:
        saved = self._policies.upsert_config(config)
        self._session.commit()
        return saved

    def get_trainer_generation_policy(self, trainer_user_id: str) -> GenerationPolicyConfig:
        return self._trainer_policies.get_config(trainer_user_id)

    def upsert_trainer_generation_policy(
        self,
        trainer_user_id: str,
        config: GenerationPolicyConfig,
    ) -> GenerationPolicyConfig:
        saved = self._trainer_policies.upsert_config(trainer_user_id, config)
        self._session.commit()
        return saved

    def get_active_plan(self, command: GetActivePlanCommand) -> TrainingPlan:
        plan = self._plans.find_active_by_user(command.user_id)
        if plan is None:
            raise PlanNotFoundError("active plan not found")
        return self._mapper.to_domain(plan)

    def get_trainer_client_plan(self, command: GetTrainerClientPlanCommand) -> TrainingPlan:
        plan = self._require_trainer_plan(command.client_user_id, command.trainer_user_id)
        return self._mapper.to_domain(plan)

    def create_empty_plan(self, command: CreateEmptyPlanCommand) -> TrainingPlan:
        if self._plans.find_active_by_user(command.client_user_id) is not None:
            raise ConflictError("user already has an active plan")
        if command.day_count < 0 or command.day_count > 28:
            raise ValidationError("day_count must be between 0 and 28")
        goal = TrainingGoal.from_raw(command.goal)
        level = TrainingLevel.from_raw(command.level)
        workouts_per_week = self._normalize_workouts_per_week(command.workouts_per_week)
        start = command.start_date if command.start_date is not None else date.today()
        end = start if command.day_count == 0 else start + timedelta(days=command.day_count - 1)
        plan_id = str(uuid4())
        try:
            plan_model = self._plans.add(
                TrainingPlanModel(
                    plan_id=plan_id,
                    source="trainer",
                    trainer_user_id=command.trainer_user_id,
                    user_id=command.client_user_id,
                    status="active",
                    goal=goal.value,
                    level=level.name.lower(),
                    workouts_per_week=workouts_per_week,
                    start_date=start,
                    end_date=end,
                )
            )
            for offset in range(command.day_count):
                scheduled = start + timedelta(days=offset)
                self._days.add(
                    PlanDayModel(
                        day_id=str(uuid4()),
                        plan_id=plan_id,
                        day_index=offset + 1,
                        scheduled_for=scheduled,
                        week=(offset // 7) + 1,
                        day_of_week=scheduled.weekday(),
                        volume_multiplier=1.0,
                    )
                )
            self._note_trainer_plan_change(plan_model, created=True)
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError("user already has an active plan") from exc
        self._session.refresh(plan_model)
        return self._mapper.to_domain(plan_model)

    def replace_plan_day_slots(self, command: ReplacePlanDaySlotsCommand) -> PlanDay:
        plan = self._require_trainer_plan(command.client_user_id, command.trainer_user_id)
        day = self._require_plan_day(plan, command.day_index)
        if len(command.slots) > self._MAX_DAY_SLOTS:
            raise ValidationError(f"a day can contain at most {self._MAX_DAY_SLOTS} exercises")
        prepared = [
            self._make_slot_line(
                day_id=day.day_id,
                exercise=self._require_slot_exercise(command.trainer_user_id, slot.exercise_id),
                slot=slot,
                sort_order=index,
            )
            for index, slot in enumerate(command.slots, start=1)
        ]
        for line in list(day.exercises):
            self._lines.delete(line)
        for model in prepared:
            self._lines.add(model)
        return self._commit_day(plan, day)

    def add_plan_slot(self, command: AddPlanSlotCommand) -> PlanDay:
        plan = self._require_trainer_plan(command.client_user_id, command.trainer_user_id)
        day = self._require_plan_day(plan, command.day_index)
        if len(list(day.exercises)) >= self._MAX_DAY_SLOTS:
            raise ValidationError(f"a day can contain at most {self._MAX_DAY_SLOTS} exercises")
        exercise = self._require_slot_exercise(command.trainer_user_id, command.slot.exercise_id)
        next_order = max((line.sort_order for line in day.exercises), default=0) + 1
        self._lines.add(
            self._make_slot_line(
                day_id=day.day_id,
                exercise=exercise,
                slot=command.slot,
                sort_order=next_order,
            )
        )
        return self._commit_day(plan, day)

    def update_plan_slot(self, command: UpdatePlanSlotCommand) -> PlanDay:
        plan = self._require_trainer_plan(command.client_user_id, command.trainer_user_id)
        day = self._require_plan_day(plan, command.day_index)
        line = self._lines.find_by_day_and_line(day.day_id, command.line_id)
        if line is None:
            raise PlanNotFoundError("plan exercise not found")
        self._apply_slot_dosage(line, command.trainer_user_id, command)
        return self._commit_day(plan, day)

    def delete_plan_slot(self, command: DeletePlanSlotCommand) -> None:
        plan = self._require_trainer_plan(command.client_user_id, command.trainer_user_id)
        day = self._require_plan_day(plan, command.day_index)
        line = self._lines.find_by_day_and_line(day.day_id, command.line_id)
        if line is None:
            raise PlanNotFoundError("plan exercise not found")
        self._lines.delete(line)
        self._renumber_slots(day)
        self._touch_plan(plan)
        self._note_trainer_plan_change(plan, created=False)
        self._session.commit()

    def reorder_plan_slots(self, command: ReorderPlanSlotsCommand) -> PlanDay:
        plan = self._require_trainer_plan(command.client_user_id, command.trainer_user_id)
        day = self._require_plan_day(plan, command.day_index)
        current_ids = {line.line_id for line in day.exercises}
        if len(command.line_ids) != len(set(command.line_ids)) or set(command.line_ids) != current_ids:
            raise ValidationError("line_ids must list every exercise on the day exactly once")
        by_id = {line.line_id: line for line in day.exercises}
        for index, line_id in enumerate(command.line_ids, start=1):
            by_id[line_id].sort_order = index
        return self._commit_day(plan, day)

    def add_plan_day(self, command: AddPlanDayCommand) -> TrainingPlan:
        plan = self._require_trainer_plan(command.client_user_id, command.trainer_user_id)
        self._validate_week_and_weekday(command.week, command.day_of_week)
        if self._days.count_for_plan(plan.plan_id) >= self._MAX_PLAN_DAYS:
            raise ValidationError(f"a plan can contain at most {self._MAX_PLAN_DAYS} days")
        if self._days.find_by_plan_week_and_weekday(plan.plan_id, command.week, command.day_of_week) is not None:
            raise ConflictError("plan day already exists")
        # day_index уже выданных дней не сдвигаем: клиент завершает тренировку по нему.
        self._create_plan_day(
            plan,
            week=command.week,
            day_of_week=command.day_of_week,
            scheduled_time=self._parse_scheduled_time(command.scheduled_time),
            volume_multiplier=1.0,
        )
        return self._commit_plan(plan)

    def remove_plan_day(self, command: RemovePlanDayCommand) -> TrainingPlan:
        plan = self._require_trainer_plan(command.client_user_id, command.trainer_user_id)
        day = self._require_plan_day(plan, command.day_index)
        self._days.delete(day)
        self._refresh_plan_end_date(plan)
        return self._commit_plan(plan)

    def update_plan_day(self, command: UpdatePlanDayCommand) -> PlanDay:
        plan = self._require_trainer_plan(command.client_user_id, command.trainer_user_id)
        day = self._require_plan_day(plan, command.day_index)
        if not command.scheduled_time_specified:
            raise ValidationError("scheduled_time is required")
        day.scheduled_time = self._parse_scheduled_time(command.scheduled_time)
        return self._commit_day(plan, day)

    def copy_plan_day(self, command: CopyPlanDayCommand) -> TrainingPlan:
        plan = self._require_trainer_plan(command.client_user_id, command.trainer_user_id)
        source = self._require_plan_day(plan, command.day_index)
        self._validate_week_and_weekday(command.week, command.day_of_week)
        self._validate_copy_mode(command.mode)
        if source.week == command.week and source.day_of_week == command.day_of_week:
            raise ValidationError("cannot copy a day onto itself")
        target = self._days.find_by_plan_week_and_weekday(plan.plan_id, command.week, command.day_of_week)
        self._ensure_copy_fits(plan, source, target, command.mode)
        if target is None:
            # Новому дню переносим плановое время источника. Уже существующий день своё время сохраняет.
            target = self._create_plan_day(
                plan,
                week=command.week,
                day_of_week=command.day_of_week,
                scheduled_time=source.scheduled_time,
                volume_multiplier=source.volume_multiplier,
            )
        self._copy_slots(source, target, mode=command.mode)
        return self._commit_plan(plan)

    def copy_plan_week(self, command: CopyPlanWeekCommand) -> TrainingPlan:
        plan = self._require_trainer_plan(command.client_user_id, command.trainer_user_id)
        self._validate_week_and_weekday(command.week, 0)
        self._validate_week_and_weekday(command.target_week, 0)
        self._validate_copy_mode(command.mode)
        if command.target_week == command.week:
            raise ValidationError("target week must differ from the source week")
        days = self._days.list_for_plan(plan.plan_id)
        sources = [day for day in days if day.week == command.week]
        if not sources:
            raise ValidationError("source week has no days")
        weekdays = [day.day_of_week for day in sources]
        if len(weekdays) != len(set(weekdays)):
            raise ValidationError("source week has two days on the same weekday")
        targets_by_weekday = {day.day_of_week: day for day in days if day.week == command.target_week}
        missing = [day for day in sources if day.day_of_week not in targets_by_weekday]
        if len(days) + len(missing) > self._MAX_PLAN_DAYS:
            raise ValidationError(f"a plan can contain at most {self._MAX_PLAN_DAYS} days")
        for source in sources:
            target = targets_by_weekday.get(source.day_of_week)
            self._ensure_slot_room(source, target, command.mode)
        for source in sorted(sources, key=lambda item: item.day_of_week):
            target = targets_by_weekday.get(source.day_of_week)
            if target is None:
                target = self._create_plan_day(
                    plan,
                    week=command.target_week,
                    day_of_week=source.day_of_week,
                    scheduled_time=source.scheduled_time,
                    volume_multiplier=source.volume_multiplier,
                )
            self._copy_slots(source, target, mode=command.mode)
        return self._commit_plan(plan)

    def require_plan(self, plan_id: str) -> TrainingPlan:
        plan = self._plans.find_by_id(plan_id)
        if plan is None:
            raise PlanNotFoundError("plan not found")
        return self._mapper.to_domain(plan)

    def get_plan_day(self, command: GetPlanDayCommand) -> PlanDay:
        plan = self._plans.find_by_id(command.plan_id)
        if plan is None:
            raise PlanNotFoundError("plan not found")
        day = self._days.find_by_plan_and_index(command.plan_id, command.day_index)
        if day is None:
            raise PlanNotFoundError("plan day not found")
        return self._mapper.day_to_domain(day)

    def get_today_workout(self, command: GetTodayWorkoutCommand) -> TodayWorkout:
        plan = self._plans.find_active_by_user(command.user_id)
        if plan is None:
            raise PlanNotFoundError("active plan not found")
        day = self._days.find_by_plan_and_date(plan.plan_id, date.today())
        if day is None or not day.exercises:
            raise PlanNotFoundError("today workout not found")
        return TodayWorkout(
            plan_id=plan.plan_id,
            source=plan.source,
            trainer_user_id=plan.trainer_user_id,
            day=self._mapper.day_to_domain(day),
        )

    def complete_plan_day(self, command: CompletePlanDayCommand) -> TodayWorkout:
        plan = self._plans.find_active_by_user(command.user_id)
        if plan is None:
            raise PlanNotFoundError("active plan not found")
        day = self._days.find_by_plan_and_index(plan.plan_id, command.day_index)
        if day is None or not day.exercises:
            raise PlanNotFoundError("plan day not found")
        if day.is_completed:
            raise ConflictError("workout already completed")
        # completed_at остаётся финишем для старых клиентов. finished_at — то же событие.
        # started_at пишем только если клиент его прислал: сервер старт сам не выдумывает.
        finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
        day.is_completed = True
        day.completed_at = finished_at
        day.finished_at = finished_at
        day.started_at = self._normalize_started_at(command.started_at, finished_at)
        self._session.commit()
        self._session.refresh(day)
        return TodayWorkout(
            plan_id=plan.plan_id,
            source=plan.source,
            trainer_user_id=plan.trainer_user_id,
            day=self._mapper.day_to_domain(day),
        )

    def replace_plan_exercise(self, command: ReplacePlanExerciseCommand) -> TodayWorkout:
        plan = self._plans.find_active_by_user(command.user_id)
        if plan is None:
            raise PlanNotFoundError("active plan not found")
        day = self._days.find_by_plan_and_index(plan.plan_id, command.day_index)
        if day is None or not day.exercises:
            raise PlanNotFoundError("plan day not found")
        if day.is_completed:
            raise ConflictError("cannot replace exercise in completed workout")
        line = self._lines.find_by_day_and_line(day.day_id, command.line_id)
        if line is None:
            raise PlanNotFoundError("plan exercise not found")

        existing_ids = {item.exercise_id for item in day.exercises}
        replacement = self._pick_replacement_exercise(
            plan_source=plan.source,
            trainer_user_id=plan.trainer_user_id,
            current_exercise_id=line.exercise_id,
            current_category=line.category,
            current_is_cardio=line.is_cardio,
            existing_exercise_ids=existing_ids,
        )
        if replacement is None:
            raise ValidationError("no replacement exercise available")

        line.exercise_id = str(replacement["exercise_id"])
        line.exercise_name = str(replacement["exercise_name"])
        line.category = str(replacement["category"])
        line.is_cardio = bool(replacement["is_cardio"])

        is_hold = bool(replacement["is_hold"])
        if is_hold:
            line.reps = None
            if line.duration_seconds is None:
                line.duration_seconds = int(replacement["default_duration_seconds"] or 35)
        else:
            line.duration_seconds = None
            if line.reps is None:
                line.reps = int(replacement["default_reps"] or 10)
        if line.sets is None:
            line.sets = int(replacement["default_sets"] or 3)
        if line.rest_seconds is None:
            line.rest_seconds = int(replacement["default_rest_seconds"] or 60)

        working_weight = self._resolve_working_weight_for_plan(
            plan=plan,
            exercise_row_id=line.exercise_id,
            default_weight_kg=replacement.get("default_weight_kg"),
        )
        result = build_prescriptions(
            working_weight=working_weight,
            sets=line.sets or int(replacement["default_sets"] or 3),
            load_scheme=str(replacement["load_scheme"]),
            scheme_steps=list(replacement["scheme_steps"]),  # type: ignore[arg-type]
            is_hold=is_hold,
            reps=line.reps,
            duration_seconds=line.duration_seconds,
            rest_seconds=line.rest_seconds,
        )
        line.sets = line.sets or int(replacement["default_sets"] or 3)
        line.weight_kg = result.weight_kg
        if is_hold:
            line.duration_seconds = result.duration_seconds
        line.set_prescriptions_json = dumps_set_prescriptions(list(result.set_prescriptions))

        self._session.commit()
        self._session.refresh(day)
        return TodayWorkout(
            plan_id=plan.plan_id,
            source=plan.source,
            trainer_user_id=plan.trainer_user_id,
            day=self._mapper.day_to_domain(day),
        )

    def _pick_replacement_exercise(
        self,
        *,
        plan_source: str,
        trainer_user_id: str | None,
        current_exercise_id: str,
        current_category: str,
        current_is_cardio: bool,
        existing_exercise_ids: set[str],
    ) -> dict[str, object] | None:
        candidates: list[dict[str, object]] = []
        if plan_source == "system":
            for item in self._platform_exercises.list_all(include_archived=False):
                candidates.append(self._catalog_exercise_as_replacement(item))
        else:
            if not trainer_user_id:
                return None
            self._ensure_trainer_catalog_baseline(trainer_user_id)
            for item in self._trainer_exercises.list_by_trainer(trainer_user_id, include_archived=False):
                candidates.append(self._catalog_exercise_as_replacement(item))

        primary = [
            item
            for item in candidates
            if self._is_replacement_candidate(
                item,
                current_exercise_id=current_exercise_id,
                current_category=current_category,
                current_is_cardio=current_is_cardio,
                existing_exercise_ids=existing_exercise_ids,
                require_same_category=True,
            )
        ]
        if primary:
            return primary[0]
        fallback = [
            item
            for item in candidates
            if self._is_replacement_candidate(
                item,
                current_exercise_id=current_exercise_id,
                current_category=current_category,
                current_is_cardio=current_is_cardio,
                existing_exercise_ids=existing_exercise_ids,
                require_same_category=False,
            )
        ]
        return fallback[0] if fallback else None

    @staticmethod
    def _catalog_exercise_as_replacement(
        item: TrainerExerciseModel | PlatformExerciseModel,
    ) -> dict[str, object]:
        return {
            "exercise_id": item.row_id,
            "exercise_name": item.exercise_name,
            "category": item.workout_category,
            "is_cardio": item.is_cardio,
            "is_hold": item.is_hold,
            "load_scheme": item.load_scheme,
            "scheme_steps": parse_scheme_steps(item.scheme_steps_json),
            "default_sets": item.default_sets,
            "default_reps": item.default_reps,
            "default_duration_seconds": item.default_duration_seconds,
            "default_rest_seconds": item.default_rest_seconds,
            "default_weight_kg": item.default_weight_kg,
        }

    def _resolve_working_weight_for_plan(
        self,
        *,
        plan: TrainingPlanModel,
        exercise_row_id: str,
        default_weight_kg: object,
    ) -> float | None:
        if plan.source == "system":
            load = self._client_loads.find_platform(plan.user_id, exercise_row_id)
        elif plan.trainer_user_id:
            load = self._client_loads.find(plan.user_id, plan.trainer_user_id, exercise_row_id)
        else:
            load = None
        if load is not None:
            return float(load.working_weight_kg)
        if default_weight_kg is None:
            return None
        return float(default_weight_kg)

    def _apply_weights_to_line(
        self,
        line: PlanExerciseModel,
        *,
        working_weight: float,
        load_scheme: str,
        scheme_steps: list[float],
        is_hold: bool,
    ) -> None:
        existing = parse_set_prescriptions(line.set_prescriptions_json)
        result = rescale_plan_line_weights(
            working_weight=working_weight,
            load_scheme=load_scheme,
            scheme_steps=scheme_steps,
            is_hold=is_hold,
            sets=line.sets,
            reps=line.reps,
            duration_seconds=line.duration_seconds,
            rest_seconds=line.rest_seconds,
            existing_prescriptions=existing,
        )
        line.weight_kg = result.weight_kg
        line.set_prescriptions_json = dumps_set_prescriptions(list(result.set_prescriptions))

    def _patch_active_plan_exercise_weights(
        self,
        *,
        client_user_id: str,
        exercise_row_id: str,
        working_weight_kg: float,
        plan_source: str,
        trainer_user_id: str | None,
        load_scheme: str,
        scheme_steps: list[float],
        is_hold: bool,
    ) -> None:
        plan = self._plans.find_active_by_user(client_user_id)
        if plan is None or plan.source != plan_source:
            return
        if plan_source == "trainer" and plan.trainer_user_id != trainer_user_id:
            return
        for day in plan.days:
            if day.is_completed:
                continue
            for line in day.exercises:
                if line.exercise_id != exercise_row_id:
                    continue
                self._apply_weights_to_line(
                    line,
                    working_weight=working_weight_kg,
                    load_scheme=load_scheme,
                    scheme_steps=scheme_steps,
                    is_hold=is_hold,
                )

    @staticmethod
    def _is_replacement_candidate(
        item: dict[str, object],
        *,
        current_exercise_id: str,
        current_category: str,
        current_is_cardio: bool,
        existing_exercise_ids: set[str],
        require_same_category: bool,
    ) -> bool:
        exercise_id = str(item["exercise_id"])
        if exercise_id == current_exercise_id or exercise_id in existing_exercise_ids:
            return False
        if bool(item["is_cardio"]) != current_is_cardio:
            return False
        if require_same_category and str(item["category"]) != current_category:
            return False
        return True

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

    def list_client_platform_loads(self, command: ListClientPlatformLoadsCommand) -> list[ClientExerciseLoad]:
        rows = self._client_loads.list_for_client_platform(command.client_user_id)
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
        self._patch_active_plan_exercise_weights(
            client_user_id=command.client_user_id,
            exercise_row_id=command.exercise_row_id,
            working_weight_kg=float(command.working_weight_kg),
            plan_source="trainer",
            trainer_user_id=command.trainer_user_id,
            load_scheme=exercise.load_scheme,
            scheme_steps=parse_scheme_steps(exercise.scheme_steps_json),
            is_hold=bool(exercise.is_hold),
        )
        self._session.commit()
        self._session.refresh(model)
        return self._mapper.client_load_to_domain(model)

    def upsert_client_platform_load(self, command: UpsertClientPlatformLoadCommand) -> ClientExerciseLoad:
        if command.working_weight_kg <= 0:
            raise ValidationError("working_weight_kg must be > 0")
        self._ensure_platform_catalog_baseline()
        exercise = self._platform_exercises.find_by_row_id(command.exercise_row_id)
        if exercise is None or not exercise.is_active:
            raise PlatformExerciseNotFoundError("platform exercise not found")
        model = self._client_loads.upsert_platform(
            client_user_id=command.client_user_id,
            exercise_row_id=command.exercise_row_id,
            working_weight_kg=float(command.working_weight_kg),
        )
        self._patch_active_plan_exercise_weights(
            client_user_id=command.client_user_id,
            exercise_row_id=command.exercise_row_id,
            working_weight_kg=float(command.working_weight_kg),
            plan_source="system",
            trainer_user_id=None,
            load_scheme=exercise.load_scheme,
            scheme_steps=parse_scheme_steps(exercise.scheme_steps_json),
            is_hold=bool(exercise.is_hold),
        )
        self._session.commit()
        self._session.refresh(model)
        return self._mapper.client_load_to_domain(model)

    def list_active_platform_exercises(self) -> list[PlatformExercise]:
        rows = self._ensure_platform_catalog_baseline()
        return [self._mapper.platform_exercise_to_domain(item) for item in rows]

    def add_trainer_exercise(self, command: AddTrainerExerciseCommand) -> TrainerExercise:
        primary, secondary = self._normalize_muscle_lists(command.primary_muscles, command.secondary_muscles)
        workout_category = derive_workout_category(primary)
        self._validate_exercise_fields(
            command.equipment,
            command.difficulty,
            workout_category,
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
            workout_category=workout_category,
            default_sets=sets,
            default_reps=reps,
            default_duration_seconds=duration,
            default_rest_seconds=rest,
            default_weight_kg=weight,
            load_scheme=scheme,
            scheme_steps_json=self._mapper.dumps_scheme_steps(steps),
            is_active=True,
            video_url=None,
            start_image_url=None,
            end_image_url=None,
        )
        self._trainer_exercises.add(model)
        self._exercise_muscles.replace_trainer_muscles(
            model.row_id,
            primary=primary,
            secondary=secondary,
        )
        self._session.commit()
        self._session.refresh(model)
        return self._mapper.trainer_exercise_to_domain(model)

    def update_trainer_exercise(self, command: UpdateTrainerExerciseCommand) -> TrainerExercise:
        primary, secondary = self._normalize_muscle_lists(command.primary_muscles, command.secondary_muscles)
        workout_category = derive_workout_category(primary)
        self._validate_exercise_fields(
            command.equipment,
            command.difficulty,
            workout_category,
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
        model.workout_category = workout_category
        model.default_sets = sets
        model.default_reps = reps
        model.default_duration_seconds = duration
        model.default_rest_seconds = rest
        model.default_weight_kg = weight
        model.load_scheme = scheme
        model.scheme_steps_json = self._mapper.dumps_scheme_steps(steps)
        self._exercise_muscles.replace_trainer_muscles(
            model.row_id,
            primary=primary,
            secondary=secondary,
        )
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

    def archive_trainer_exercise(self, command: ArchiveTrainerExerciseCommand) -> list[str]:
        model = self._trainer_exercises.find_by_trainer_and_row_id(command.trainer_user_id, command.row_id)
        if model is None:
            raise TrainerExerciseNotFoundError("trainer exercise not found")
        # Архив отпускает медиа: восстановление упражнения файлы не возвращает.
        detached = _detach_media_keys(model)
        model.is_active = False
        self._session.commit()
        return detached

    def restore_trainer_exercise(self, command: RestoreTrainerExerciseCommand) -> None:
        model = self._trainer_exercises.find_by_trainer_and_row_id(command.trainer_user_id, command.row_id)
        if model is None:
            raise TrainerExerciseNotFoundError("trainer exercise not found")
        if model.is_active:
            return
        model.is_active = True
        self._session.commit()

    def list_platform_exercises(self, command: ListPlatformExercisesCommand) -> tuple[list[PlatformExercise], int]:
        page = max(command.page, 1)
        page_size = min(max(command.page_size, 1), 100)
        offset = (page - 1) * page_size
        rows, total = self._platform_exercises.list_page(
            include_archived=command.include_archived,
            offset=offset,
            limit=page_size,
        )
        return [self._mapper.platform_exercise_to_domain(item) for item in rows], total

    def get_platform_exercise(self, row_id: str) -> PlatformExercise:
        model = self._platform_exercises.find_by_row_id(row_id)
        if model is None:
            raise PlatformExerciseNotFoundError("platform exercise not found")
        return self._mapper.platform_exercise_to_domain(model)

    def get_active_platform_exercise(self, row_id: str) -> PlatformExercise:
        exercise = self.get_platform_exercise(row_id)
        if not exercise.is_active:
            raise PlatformExerciseNotFoundError("platform exercise not found")
        return exercise

    def add_platform_exercise(self, command: AddPlatformExerciseCommand) -> PlatformExercise:
        primary, secondary = self._normalize_muscle_lists(command.primary_muscles, command.secondary_muscles)
        workout_category = derive_workout_category(primary)
        self._validate_exercise_fields(
            command.equipment,
            command.difficulty,
            workout_category,
            command.is_hold,
            command.default_sets,
            command.default_reps,
            command.default_duration_seconds,
            command.default_rest_seconds,
            command.default_weight_kg,
            command.load_scheme,
            command.scheme_steps,
        )
        catalog_key = self._normalize_catalog_key(command.catalog_key)
        if catalog_key is not None and self._platform_exercises.find_by_catalog_key(catalog_key) is not None:
            raise ConflictError("platform exercise with this catalog_key already exists")
        sets, reps, duration, rest, weight = self._normalize_baseline(
            command.is_hold,
            command.default_sets,
            command.default_reps,
            command.default_duration_seconds,
            command.default_rest_seconds,
            command.default_weight_kg,
        )
        scheme, steps = self._normalize_scheme(command.load_scheme, command.scheme_steps, command.is_hold)
        model = PlatformExerciseModel(
            row_id=str(uuid4()),
            catalog_key=catalog_key,
            exercise_name=command.exercise_name.strip(),
            description=(command.description.strip() if command.description and command.description.strip() else None),
            equipment=self._normalize_stored_equipment(command.equipment),
            is_cardio=command.is_cardio,
            is_hold=command.is_hold,
            difficulty=command.difficulty,
            workout_category=workout_category,
            default_sets=sets,
            default_reps=reps,
            default_duration_seconds=duration,
            default_rest_seconds=rest,
            default_weight_kg=weight,
            load_scheme=scheme,
            scheme_steps_json=self._mapper.dumps_scheme_steps(steps),
            is_active=True,
            video_url=None,
            start_image_url=None,
            end_image_url=None,
        )
        self._platform_exercises.add(model)
        self._exercise_muscles.replace_platform_muscles(
            model.row_id,
            primary=primary,
            secondary=secondary,
        )
        self._session.commit()
        self._session.refresh(model)
        return self._mapper.platform_exercise_to_domain(model)

    def update_platform_exercise(self, command: UpdatePlatformExerciseCommand) -> PlatformExercise:
        primary, secondary = self._normalize_muscle_lists(command.primary_muscles, command.secondary_muscles)
        workout_category = derive_workout_category(primary)
        self._validate_exercise_fields(
            command.equipment,
            command.difficulty,
            workout_category,
            command.is_hold,
            command.default_sets,
            command.default_reps,
            command.default_duration_seconds,
            command.default_rest_seconds,
            command.default_weight_kg,
            command.load_scheme,
            command.scheme_steps,
        )
        model = self._platform_exercises.find_by_row_id(command.row_id)
        if model is None:
            raise PlatformExerciseNotFoundError("platform exercise not found")
        catalog_key = self._normalize_catalog_key(command.catalog_key)
        if catalog_key is not None:
            existing = self._platform_exercises.find_by_catalog_key(catalog_key)
            if existing is not None and existing.row_id != model.row_id:
                raise ConflictError("platform exercise with this catalog_key already exists")
        sets, reps, duration, rest, weight = self._normalize_baseline(
            command.is_hold,
            command.default_sets,
            command.default_reps,
            command.default_duration_seconds,
            command.default_rest_seconds,
            command.default_weight_kg,
        )
        scheme, steps = self._normalize_scheme(command.load_scheme, command.scheme_steps, command.is_hold)
        model.catalog_key = catalog_key
        model.exercise_name = command.exercise_name.strip()
        model.description = command.description.strip() if command.description and command.description.strip() else None
        model.equipment = self._normalize_stored_equipment(command.equipment)
        model.is_cardio = command.is_cardio
        model.is_hold = command.is_hold
        model.difficulty = command.difficulty
        model.workout_category = workout_category
        model.default_sets = sets
        model.default_reps = reps
        model.default_duration_seconds = duration
        model.default_rest_seconds = rest
        model.default_weight_kg = weight
        model.load_scheme = scheme
        model.scheme_steps_json = self._mapper.dumps_scheme_steps(steps)
        self._exercise_muscles.replace_platform_muscles(
            model.row_id,
            primary=primary,
            secondary=secondary,
        )
        if not model.is_active:
            model.is_active = True
        self._session.commit()
        self._session.refresh(model)
        return self._mapper.platform_exercise_to_domain(model)

    def archive_platform_exercise(self, command: ArchivePlatformExerciseCommand) -> list[str]:
        model = self._platform_exercises.find_by_row_id(command.row_id)
        if model is None:
            raise PlatformExerciseNotFoundError("platform exercise not found")
        detached = _detach_media_keys(model)
        model.is_active = False
        self._session.commit()
        return detached

    def admin_list_exercises(
        self,
        *,
        trainer_user_id: str | None,
        include_archived: bool,
        page: int,
        page_size: int,
    ) -> tuple[list[TrainerExercise], int]:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 100)
        offset = (page - 1) * page_size
        rows, total = self._trainer_exercises.list_all(
            trainer_user_id=trainer_user_id,
            include_archived=include_archived,
            offset=offset,
            limit=page_size,
        )
        return [self._mapper.trainer_exercise_to_domain(item) for item in rows], total

    def admin_get_active_plan(self, user_id: str) -> TrainingPlan:
        return self.get_active_plan(GetActivePlanCommand(user_id=user_id))

    def admin_list_client_loads(self, client_user_id: str, trainer_user_id: str) -> list[ClientExerciseLoad]:
        return self.list_client_loads(
            ListClientLoadsCommand(client_user_id=client_user_id, trainer_user_id=trainer_user_id)
        )

    def set_trainer_exercise_video_url(
        self,
        trainer_user_id: str,
        row_id: str,
        video_url: str,
    ) -> tuple[TrainerExercise, str | None]:
        model = self._trainer_exercises.lock_for_media_update(trainer_user_id, row_id)
        if model is None:
            raise TrainerExerciseNotFoundError("trainer exercise not found")
        previous_video_url = model.video_url
        model.video_url = video_url
        self._session.commit()
        self._session.refresh(model)
        return self._mapper.trainer_exercise_to_domain(model), previous_video_url

    def clear_trainer_exercise_video_url(self, trainer_user_id: str, row_id: str) -> tuple[TrainerExercise, str | None]:
        model = self._trainer_exercises.lock_for_media_update(trainer_user_id, row_id)
        if model is None:
            raise TrainerExerciseNotFoundError("trainer exercise not found")
        previous_video_url = model.video_url
        model.video_url = None
        self._session.commit()
        self._session.refresh(model)
        return self._mapper.trainer_exercise_to_domain(model), previous_video_url

    def set_platform_exercise_video_url(self, row_id: str, video_url: str) -> tuple[PlatformExercise, str | None]:
        model = self._platform_exercises.lock_for_media_update(row_id)
        if model is None:
            raise PlatformExerciseNotFoundError("platform exercise not found")
        previous_video_url = model.video_url
        model.video_url = video_url
        self._session.commit()
        self._session.refresh(model)
        return self._mapper.platform_exercise_to_domain(model), previous_video_url

    def clear_platform_exercise_video_url(self, row_id: str) -> tuple[PlatformExercise, str | None]:
        model = self._platform_exercises.lock_for_media_update(row_id)
        if model is None:
            raise PlatformExerciseNotFoundError("platform exercise not found")
        previous_video_url = model.video_url
        model.video_url = None
        self._session.commit()
        self._session.refresh(model)
        return self._mapper.platform_exercise_to_domain(model), previous_video_url

    def set_trainer_exercise_photo_url(
        self,
        trainer_user_id: str,
        row_id: str,
        position: str,
        image_url: str,
    ) -> tuple[TrainerExercise, str | None]:
        model = self._trainer_exercises.lock_for_media_update(trainer_user_id, row_id)
        if model is None:
            raise TrainerExerciseNotFoundError("trainer exercise not found")
        field = self._photo_url_field(position)
        previous_image_url = getattr(model, field)
        setattr(model, field, image_url)
        self._session.commit()
        self._session.refresh(model)
        return self._mapper.trainer_exercise_to_domain(model), previous_image_url

    def clear_trainer_exercise_photo_url(
        self,
        trainer_user_id: str,
        row_id: str,
        position: str,
    ) -> tuple[TrainerExercise, str | None]:
        model = self._trainer_exercises.lock_for_media_update(trainer_user_id, row_id)
        if model is None:
            raise TrainerExerciseNotFoundError("trainer exercise not found")
        field = self._photo_url_field(position)
        previous_image_url = getattr(model, field)
        setattr(model, field, None)
        self._session.commit()
        self._session.refresh(model)
        return self._mapper.trainer_exercise_to_domain(model), previous_image_url

    def set_platform_exercise_photo_url(
        self,
        row_id: str,
        position: str,
        image_url: str,
    ) -> tuple[PlatformExercise, str | None]:
        model = self._platform_exercises.lock_for_media_update(row_id)
        if model is None:
            raise PlatformExerciseNotFoundError("platform exercise not found")
        field = self._photo_url_field(position)
        previous_image_url = getattr(model, field)
        setattr(model, field, image_url)
        self._session.commit()
        self._session.refresh(model)
        return self._mapper.platform_exercise_to_domain(model), previous_image_url

    def clear_platform_exercise_photo_url(
        self,
        row_id: str,
        position: str,
    ) -> tuple[PlatformExercise, str | None]:
        model = self._platform_exercises.lock_for_media_update(row_id)
        if model is None:
            raise PlatformExerciseNotFoundError("platform exercise not found")
        field = self._photo_url_field(position)
        previous_image_url = getattr(model, field)
        setattr(model, field, None)
        self._session.commit()
        self._session.refresh(model)
        return self._mapper.platform_exercise_to_domain(model), previous_image_url

    def media_key_reference_count(self, object_key: str) -> int:
        """Сколько строк упражнений всё ещё ссылаются на ключ (включая старый URL)."""
        variants = media_key_variants(object_key)
        if not variants:
            return 0
        total = 0
        for model in (TrainerExerciseModel, PlatformExerciseModel):
            predicate = or_(
                model.video_url.in_(variants),
                model.start_image_url.in_(variants),
                model.end_image_url.in_(variants),
            )
            total += int(self._session.scalar(select(func.count()).select_from(model).where(predicate)) or 0)
        return total

    @staticmethod
    def _photo_url_field(position: str) -> str:
        if position == "start":
            return "start_image_url"
        if position == "end":
            return "end_image_url"
        raise ValidationError("invalid photo position (allowed: start, end)")

    def _create_plan_day(
        self,
        plan: TrainingPlanModel,
        *,
        week: int,
        day_of_week: int,
        scheduled_time: time | None,
        volume_multiplier: float,
    ) -> PlanDayModel:
        scheduled = self._date_for_week_weekday(plan.start_date, week, day_of_week)
        if self._days.find_by_plan_and_date(plan.plan_id, scheduled) is not None:
            raise ConflictError("plan day already exists")
        if self._days.find_by_plan_week_and_weekday(plan.plan_id, week, day_of_week) is not None:
            raise ConflictError("plan day already exists")
        day = self._days.add(
            PlanDayModel(
                day_id=str(uuid4()),
                plan_id=plan.plan_id,
                day_index=self._days.max_day_index(plan.plan_id) + 1,
                scheduled_for=scheduled,
                week=week,
                day_of_week=day_of_week,
                volume_multiplier=volume_multiplier,
                is_completed=False,
                completed_at=None,
                scheduled_time=scheduled_time,
                started_at=None,
                finished_at=None,
            )
        )
        if scheduled > plan.end_date:
            plan.end_date = scheduled
        return day

    def _ensure_copy_fits(
        self,
        plan: TrainingPlanModel,
        source: PlanDayModel,
        target: PlanDayModel | None,
        mode: str,
    ) -> None:
        if target is None and self._days.count_for_plan(plan.plan_id) >= self._MAX_PLAN_DAYS:
            raise ValidationError(f"a plan can contain at most {self._MAX_PLAN_DAYS} days")
        self._ensure_slot_room(source, target, mode)

    def _ensure_slot_room(self, source: PlanDayModel, target: PlanDayModel | None, mode: str) -> None:
        incoming = len(list(source.exercises))
        existing = 0 if target is None or mode == "overwrite" else len(list(target.exercises))
        if existing + incoming > self._MAX_DAY_SLOTS:
            raise ValidationError(f"a day can contain at most {self._MAX_DAY_SLOTS} exercises")

    def _copy_slots(self, source: PlanDayModel, target: PlanDayModel, *, mode: str) -> None:
        sources = sorted(list(source.exercises), key=lambda item: (item.sort_order, item.line_id))
        if mode == "overwrite":
            for line in list(target.exercises):
                self._lines.delete(line)
            next_order = 1
        elif mode == "append":
            next_order = max((line.sort_order for line in target.exercises), default=0) + 1
        else:
            raise ValidationError("mode must be overwrite or append")
        for offset, line in enumerate(sources):
            self._lines.add(self._clone_slot_line(line, target.day_id, next_order + offset))

    @staticmethod
    def _clone_slot_line(source: PlanExerciseModel, day_id: str, sort_order: int) -> PlanExerciseModel:
        return PlanExerciseModel(
            line_id=str(uuid4()),
            day_id=day_id,
            exercise_id=source.exercise_id,
            exercise_name=source.exercise_name,
            category=source.category,
            is_cardio=source.is_cardio,
            sort_order=sort_order,
            sets=source.sets,
            reps=source.reps,
            duration_seconds=source.duration_seconds,
            rest_seconds=source.rest_seconds,
            weight_kg=source.weight_kg,
            set_prescriptions_json=source.set_prescriptions_json,
            note=source.note,
        )

    def _refresh_plan_end_date(self, plan: TrainingPlanModel) -> None:
        # start_date — якорь недель, его не двигаем, иначе съедут уже созданные дни.
        latest = self._days.max_scheduled_for(plan.plan_id)
        plan.end_date = plan.start_date if latest is None or latest < plan.start_date else latest

    def _commit_plan(self, plan: TrainingPlanModel) -> TrainingPlan:
        self._touch_plan(plan)
        self._note_trainer_plan_change(plan, created=False)
        self._session.commit()
        self._session.refresh(plan)
        return self._mapper.to_domain(plan)

    def _validate_week_and_weekday(self, week: int, day_of_week: int) -> None:
        if week < 1 or week > self._MAX_WEEK:
            raise ValidationError(f"week must be between 1 and {self._MAX_WEEK}")
        if day_of_week < 0 or day_of_week > 6:
            raise ValidationError("day_of_week must be between 0 and 6 (Monday is 0)")

    @staticmethod
    def _validate_copy_mode(mode: str) -> None:
        if mode not in {"overwrite", "append"}:
            raise ValidationError("mode must be overwrite or append")

    @staticmethod
    def _date_for_week_weekday(start: date, week: int, day_of_week: int) -> date:
        # Неделя плана — окно в 7 дней от start_date, а не календарная неделя.
        # В таком окне каждый weekday встречается один раз.
        week_start = start + timedelta(days=(week - 1) * 7)
        offset = (day_of_week - week_start.weekday()) % 7
        return week_start + timedelta(days=offset)

    @staticmethod
    def _parse_scheduled_time(value: str | None) -> time | None:
        if value is None:
            return None
        try:
            return datetime.strptime(value, "%H:%M").time()
        except ValueError as exc:
            raise ValidationError("scheduled_time must be HH:MM") from exc

    def _clean_note(self, note: str | None) -> str | None:
        if note is None:
            return None
        cleaned = note.strip()
        if not cleaned:
            return None
        if len(cleaned) > self._MAX_NOTE_LENGTH:
            raise ValidationError(f"note must be at most {self._MAX_NOTE_LENGTH} characters")
        return cleaned

    def _normalize_started_at(self, started_at: datetime | None, finished_at: datetime) -> datetime | None:
        if started_at is None:
            return None
        if started_at.tzinfo is None:
            normalized = started_at
        else:
            normalized = started_at.astimezone(timezone.utc).replace(tzinfo=None)
        if normalized > finished_at:
            raise ValidationError("started_at must not be after the workout finish time")
        if finished_at - normalized > timedelta(days=7):
            raise ValidationError("started_at is too far before the workout finish time")
        return normalized

    def _require_trainer_plan(self, client_user_id: str, trainer_user_id: str) -> TrainingPlanModel:
        plan = self._plans.find_active_by_user(client_user_id)
        if plan is None or plan.source != "trainer" or plan.trainer_user_id != trainer_user_id:
            raise PlanNotFoundError("active plan not found")
        return plan

    def _require_plan_day(self, plan: TrainingPlanModel, day_index: int) -> PlanDayModel:
        if day_index < 1:
            raise ValidationError("day_index must be >= 1")
        day = self._days.find_by_plan_and_index(plan.plan_id, day_index)
        if day is None:
            raise PlanNotFoundError("plan day not found")
        return day

    def _require_slot_exercise(self, trainer_user_id: str, exercise_id: str) -> TrainerExerciseModel:
        cleaned = exercise_id.strip()
        if not cleaned:
            raise ValidationError("exercise_id is required")
        exercise = self._trainer_exercises.find_by_trainer_and_row_id(trainer_user_id, cleaned)
        if exercise is None:
            raise TrainerExerciseNotFoundError("trainer exercise not found")
        if not exercise.is_active:
            raise ValidationError("cannot add an archived exercise")
        return exercise

    def _make_slot_line(
        self,
        *,
        day_id: str,
        exercise: TrainerExerciseModel,
        slot: PlanSlotInput,
        sort_order: int,
    ) -> PlanExerciseModel:
        sets, reps, duration, rest, weight = self._resolve_new_slot_dosage(exercise, slot)
        prescriptions = build_prescriptions(
            working_weight=weight,
            sets=sets,
            load_scheme=(exercise.load_scheme or "flat").strip().lower(),
            scheme_steps=parse_scheme_steps(exercise.scheme_steps_json),
            is_hold=exercise.is_hold,
            reps=reps,
            duration_seconds=duration,
            rest_seconds=rest,
        )
        return PlanExerciseModel(
            line_id=str(uuid4()),
            day_id=day_id,
            exercise_id=exercise.row_id,
            exercise_name=exercise.exercise_name,
            category=exercise.workout_category,
            is_cardio=exercise.is_cardio,
            sort_order=sort_order,
            sets=sets,
            reps=reps,
            duration_seconds=duration,
            rest_seconds=rest,
            weight_kg=weight,
            set_prescriptions_json=self._mapper.dumps_set_prescriptions(list(prescriptions.set_prescriptions)),
            note=self._clean_note(slot.note),
        )

    def _apply_slot_dosage(
        self,
        line: PlanExerciseModel,
        trainer_user_id: str,
        command: UpdatePlanSlotCommand,
    ) -> None:
        cleaned_note = self._clean_note(command.note) if command.note_specified else None
        # The slot keeps the exercise snapshot from when it was added. Catalog
        # edits do not rewrite name, category, or hold-vs-reps mode. Scheme is
        # read only while applying this explicit dosage change.
        exercise = self._trainer_exercises.find_by_trainer_and_row_id(trainer_user_id, line.exercise_id)
        is_hold = line.reps is None and line.duration_seconds is not None
        if exercise is not None:
            scheme = (exercise.load_scheme or "flat").strip().lower()
            steps = parse_scheme_steps(exercise.scheme_steps_json)
        else:
            scheme = "flat"
            steps = []
        sets = self._pick_required_int(
            specified=command.sets_specified,
            value=command.sets,
            default=line.sets if line.sets is not None else 3,
            field="sets",
            minimum=1,
            maximum=10,
        )
        rest = self._pick_required_int(
            specified=command.rest_specified,
            value=command.rest_seconds,
            default=0 if line.rest_seconds is None else line.rest_seconds,
            field="rest_seconds",
            minimum=0,
            maximum=600,
        )
        weight = command.weight_kg if command.weight_specified else line.weight_kg
        if weight is not None and weight < 0:
            raise ValidationError("weight_kg must be >= 0")
        if is_hold:
            duration = self._pick_required_int(
                specified=command.duration_specified,
                value=command.duration_seconds,
                default=line.duration_seconds,
                field="duration_seconds",
                minimum=5,
                maximum=3600,
            )
            reps = None
        else:
            reps = self._pick_required_int(
                specified=command.reps_specified,
                value=command.reps,
                default=line.reps,
                field="reps",
                minimum=1,
                maximum=100,
            )
            duration = None
        prescriptions = build_prescriptions(
            working_weight=weight,
            sets=sets,
            load_scheme=scheme,
            scheme_steps=steps,
            is_hold=is_hold,
            reps=reps,
            duration_seconds=duration,
            rest_seconds=rest,
        )
        line.sets = sets
        line.reps = reps
        line.duration_seconds = duration
        line.rest_seconds = rest
        line.weight_kg = weight
        line.set_prescriptions_json = self._mapper.dumps_set_prescriptions(list(prescriptions.set_prescriptions))
        if command.note_specified:
            line.note = cleaned_note

    def _resolve_new_slot_dosage(
        self,
        exercise: TrainerExerciseModel,
        slot: PlanSlotInput,
    ) -> tuple[int, int | None, int | None, int, float | None]:
        sets = self._pick_required_int(
            specified=slot.sets_specified,
            value=slot.sets,
            default=exercise.default_sets,
            field="sets",
            minimum=1,
            maximum=10,
        )
        rest = self._pick_required_int(
            specified=slot.rest_specified,
            value=slot.rest_seconds,
            default=exercise.default_rest_seconds,
            field="rest_seconds",
            minimum=0,
            maximum=600,
        )
        weight = slot.weight_kg if slot.weight_specified else exercise.default_weight_kg
        if weight is not None and weight < 0:
            raise ValidationError("weight_kg must be >= 0")
        if exercise.is_hold:
            duration = self._pick_required_int(
                specified=slot.duration_specified,
                value=slot.duration_seconds,
                default=exercise.default_duration_seconds,
                field="duration_seconds",
                minimum=5,
                maximum=3600,
            )
            return sets, None, duration, rest, weight
        reps = self._pick_required_int(
            specified=slot.reps_specified,
            value=slot.reps,
            default=exercise.default_reps,
            field="reps",
            minimum=1,
            maximum=100,
        )
        return sets, reps, None, rest, weight

    @staticmethod
    def _pick_required_int(
        *,
        specified: bool,
        value: int | None,
        default: int | None,
        field: str,
        minimum: int,
        maximum: int,
    ) -> int:
        if specified:
            if value is None:
                raise ValidationError(f"{field} cannot be cleared")
            chosen = value
        else:
            if default is None:
                raise ValidationError(f"{field} is required")
            chosen = default
        if chosen < minimum or chosen > maximum:
            raise ValidationError(f"{field} must be between {minimum} and {maximum}")
        return chosen

    def _renumber_slots(self, day: PlanDayModel) -> None:
        self._session.flush()
        self._session.expire(day, ["exercises"])
        ordered = sorted(list(day.exercises), key=lambda item: (item.sort_order, item.line_id))
        for index, line in enumerate(ordered, start=1):
            line.sort_order = index

    def _commit_day(self, plan: TrainingPlanModel, day: PlanDayModel) -> PlanDay:
        self._touch_plan(plan)
        self._note_trainer_plan_change(plan, created=False)
        self._session.commit()
        self._session.refresh(day)
        return self._mapper.day_to_domain(day)

    def _note_trainer_plan_change(self, plan: TrainingPlanModel, *, created: bool) -> None:
        # Слоты сами по себе не шлют сообщение: пачка правок ждёт debounce и уходит одним текстом.
        if not plan.trainer_user_id:
            return
        self._plan_notices.mark_plan_changed(
            plan_id=plan.plan_id,
            client_user_id=plan.user_id,
            trainer_user_id=plan.trainer_user_id,
            created=created,
            now=datetime.now(timezone.utc).replace(tzinfo=None),
            debounce_seconds=self._plan_notice_debounce_seconds,
        )

    @staticmethod
    def _touch_plan(plan: TrainingPlanModel) -> None:
        plan.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    @staticmethod
    def _normalize_workouts_per_week(value: int) -> int:
        if value < 1:
            raise ValidationError("workouts_per_week must be >= 1")
        return min(value, 7)

    @staticmethod
    def _adjust_wpw_by_adherence(value: int, adherence_score: float, is_first_plan: bool) -> int:
        if is_first_plan:
            return value
        if adherence_score >= 0.8:
            return value + 1
        if adherence_score <= 0.45:
            return value - 1
        return value

    @staticmethod
    def _adherence_from_plan(plan) -> tuple[float, set[str]]:
        if plan is None or not plan.days:
            return 1.0, set()
        completed = sum(1 for day in plan.days if day.is_completed)
        adherence = round(completed / len(plan.days), 3)
        recent_ids = {
            line.exercise_id
            for day in plan.days
            for line in day.exercises
            if line.exercise_id
        }
        return adherence, recent_ids

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
    def _normalize_catalog_key(catalog_key: str | None) -> str | None:
        if catalog_key is None:
            return None
        cleaned = catalog_key.strip().lower()
        if not cleaned:
            return None
        if len(cleaned) > 64:
            raise ValidationError("catalog_key must be at most 64 characters")
        return cleaned

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

    @staticmethod
    def _available_equipment_from_catalog(
        equipment_values: list[str],
        unavailable_keys: set[str],
    ) -> set[str]:
        catalog_by_key: dict[str, str] = {}
        for raw in equipment_values:
            name = normalize_equipment_name(raw or "")
            if not name:
                continue
            catalog_by_key.setdefault(name.casefold(), name)
        return {"none"} | {name for key, name in catalog_by_key.items() if key not in unavailable_keys}

    def _ensure_platform_catalog_baseline(self):
        """Ensure platform base catalog exists; bootstrap from seed only if empty."""
        return self._platform_exercises.bootstrap_if_empty(
            SeedCatalogProvider().list_exercises(
                PlanGenerationInput(
                    source="system",
                    trainer_user_id=None,
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
        )

    def _ensure_trainer_catalog_baseline(self, trainer_user_id: str) -> None:
        existing = self._trainer_exercises.list_by_trainer(trainer_user_id, include_archived=True)
        if existing:
            return
        platform_rows = self._ensure_platform_catalog_baseline()
        copied: list[str] = []

        def _copy(source: str | None, row_id: str, slot: str) -> str | None:
            before = normalize_stored_media(source)
            stored = copy_or_share(
                self._media_storage,
                source,
                owner_id=trainer_user_id,
                row_id=row_id,
                slot=slot,
            )
            # Удалять при откате можно только новый объект, не общий ключ платформы.
            if stored and before and stored != before:
                copied.append(stored)
            return stored

        try:
            self._trainer_exercises.clone_from_platform(trainer_user_id, platform_rows, copy_media=_copy)
            self._session.commit()
        except Exception:
            self._session.rollback()
            self._discard_copied_media(copied)
            raise

    def _discard_copied_media(self, keys: list[str]) -> None:
        storage = self._media_storage
        if storage is None:
            return
        for key in keys:
            try:
                storage.delete_media_sync(key)
            except Exception:
                logger.exception("failed to delete media copied during a rolled-back clone key=%s", key)


def _detach_media_keys(model: TrainerExerciseModel | PlatformExerciseModel) -> list[str]:
    raw_values = [model.video_url, model.start_image_url, model.end_image_url]
    model.video_url = None
    model.start_image_url = None
    model.end_image_url = None
    keys: list[str] = []
    for value in raw_values:
        key = normalize_stored_media(value)
        if key:
            keys.append(key)
    return keys
