from __future__ import annotations

from datetime import date
from uuid import uuid4

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from application.generation import GenerationOrchestrator, PlanGenerationInput, SeedCatalogProvider
from application.gateways import ProfileGateway
from application.commands import (
    AddTrainerExerciseCommand,
    ArchiveTrainerExerciseCommand,
    GeneratePlanCommand,
    GetActivePlanCommand,
    GetPlanDayCommand,
    ListTrainerExercisesCommand,
    UpdateTrainerExerciseCommand,
)
from application.errors import ConflictError, PlanNotFoundError, TrainerExerciseNotFoundError, ValidationError
from application.models import PlanDayModel, PlanExerciseModel, TrainerExerciseModel, TrainingPlanModel
from application.repositories import (
    PlanDayRepository,
    PlanExerciseRepository,
    PlanMapper,
    TrainerExerciseRepository,
    TrainingPlanRepository,
)
from domain.entities import PlanDay, TrainerExercise, TrainingPlan
from domain.value_objects import EquipmentName, TrainingGoal, TrainingLevel, WorkoutLocation


class PlanService:
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
        equipment = self._resolve_equipment(command.equipment, workout_location)

        request = PlanGenerationInput(
            trainer_user_id=command.trainer_user_id,
            goal=goal,
            level=level,
            workout_location=workout_location,
            workouts_per_week=workouts_per_week,
            equipment=equipment,
            start_date=start_date,
            recent_exercise_ids=set(),
            is_first_plan=self._plans.find_active_by_user(command.user_id) is None,
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

    def add_trainer_exercise(self, command: AddTrainerExerciseCommand) -> TrainerExercise:
        self._validate_exercise_fields(command.equipment, command.difficulty, command.workout_category)
        existing = self._trainer_exercises.find_by_trainer_and_exercise_id(command.trainer_user_id, command.exercise_id)
        if existing is not None:
            raise ConflictError("exercise_id already exists for trainer")
        model = TrainerExerciseModel(
            row_id=str(uuid4()),
            trainer_user_id=command.trainer_user_id,
            exercise_id=command.exercise_id,
            exercise_name=command.exercise_name.strip(),
            equipment=command.equipment.strip().lower(),
            is_cardio=command.is_cardio,
            difficulty=command.difficulty,
            workout_category=command.workout_category.strip().lower(),
            is_active=True,
        )
        self._trainer_exercises.add(model)
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError("exercise_id already exists for trainer") from exc
        self._session.refresh(model)
        return self._mapper.trainer_exercise_to_domain(model)

    def update_trainer_exercise(self, command: UpdateTrainerExerciseCommand) -> TrainerExercise:
        self._validate_exercise_fields(command.equipment, command.difficulty, command.workout_category)
        model = self._trainer_exercises.find_by_trainer_and_exercise_id(command.trainer_user_id, command.exercise_id)
        if model is None:
            raise TrainerExerciseNotFoundError("trainer exercise not found")
        model.exercise_name = command.exercise_name.strip()
        model.equipment = command.equipment.strip().lower()
        model.is_cardio = command.is_cardio
        model.difficulty = command.difficulty
        model.workout_category = command.workout_category.strip().lower()
        if not model.is_active:
            model.is_active = True
        self._session.commit()
        self._session.refresh(model)
        return self._mapper.trainer_exercise_to_domain(model)

    def archive_trainer_exercise(self, command: ArchiveTrainerExerciseCommand) -> None:
        model = self._trainer_exercises.find_by_trainer_and_exercise_id(command.trainer_user_id, command.exercise_id)
        if model is None:
            raise TrainerExerciseNotFoundError("trainer exercise not found")
        if not model.is_active:
            return
        model.is_active = False
        self._session.commit()

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
    def _resolve_equipment(raw_equipment: list[str], workout_location: WorkoutLocation | None) -> set[EquipmentName]:
        names: set[EquipmentName] = {EquipmentName.NONE}
        for item in raw_equipment:
            parsed = EquipmentName.from_raw(item)
            if parsed is not None:
                names.add(parsed)
        if len(names) > 1:
            return names
        if workout_location == WorkoutLocation.HOME:
            return {
                EquipmentName.NONE,
                EquipmentName.DUMBBELLS,
                EquipmentName.RESISTANCE_BANDS,
                EquipmentName.KETTLEBELL,
            }
        if workout_location == WorkoutLocation.GYM:
            return {
                EquipmentName.NONE,
                EquipmentName.DUMBBELLS,
                EquipmentName.BARBELL,
                EquipmentName.RESISTANCE_BANDS,
                EquipmentName.KETTLEBELL,
                EquipmentName.TREADMILL,
                EquipmentName.OTHER,
            }
        return set(EquipmentName)

    @staticmethod
    def _validate_exercise_fields(equipment: str, difficulty: int, workout_category: str) -> None:
        if not equipment.strip():
            raise ValidationError("equipment must not be empty")
        if difficulty < 1 or difficulty > 5:
            raise ValidationError("difficulty must be between 1 and 5")
        if not workout_category.strip():
            raise ValidationError("workout_category must not be empty")

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
                equipment=set(EquipmentName),
                start_date=date.today(),
                recent_exercise_ids=set(),
                is_first_plan=True,
            )
        )
        self._trainer_exercises.ensure_baseline_for_trainer(trainer_user_id, baseline)
        self._session.commit()
