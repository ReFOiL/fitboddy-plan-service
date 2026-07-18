from application.commands import (
    AddPlatformExerciseCommand,
    AddTrainerExerciseCommand,
    ArchivePlatformExerciseCommand,
    ArchiveTrainerExerciseCommand,
    CompletePlanDayCommand,
    GeneratePlanCommand,
    GetActivePlanCommand,
    GetPlanDayCommand,
    GetTodayWorkoutCommand,
    ListClientLoadsCommand,
    ListClientPlatformLoadsCommand,
    ListPlatformExercisesCommand,
    ListTrainerExercisesCommand,
    ReplacePlanExerciseCommand,
    UpdatePlatformExerciseCommand,
    UpdateTrainerExerciseCommand,
    UpsertClientLoadCommand,
    UpsertClientPlatformLoadCommand,
)
from presentation.http.schemas import (
    GeneratePlanRequest,
    UpsertClientLoadRequest,
    UpsertPlatformExerciseRequest,
    UpsertTrainerExerciseRequest,
)


class PlanRequestFactory:
    @staticmethod
    def to_generate_command(payload: GeneratePlanRequest) -> GeneratePlanCommand:
        return GeneratePlanCommand(
            source=payload.source,
            trainer_user_id=payload.trainer_user_id,
            user_id=payload.user_id,
            goal=payload.goal,
            level=payload.level,
            workout_location=payload.workout_location,
            workouts_per_week=payload.workouts_per_week,
            unavailable_equipment=list(payload.unavailable_equipment),
            start_date=payload.start_date,
        )

    @staticmethod
    def to_get_active_command(user_id: str) -> GetActivePlanCommand:
        return GetActivePlanCommand(user_id=user_id)

    @staticmethod
    def to_get_day_command(plan_id: str, day_index: int) -> GetPlanDayCommand:
        return GetPlanDayCommand(plan_id=plan_id, day_index=day_index)

    @staticmethod
    def to_get_today_command(user_id: str) -> GetTodayWorkoutCommand:
        return GetTodayWorkoutCommand(user_id=user_id)

    @staticmethod
    def to_complete_day_command(user_id: str, day_index: int) -> CompletePlanDayCommand:
        return CompletePlanDayCommand(user_id=user_id, day_index=day_index)

    @staticmethod
    def to_replace_exercise_command(user_id: str, day_index: int, line_id: str) -> ReplacePlanExerciseCommand:
        return ReplacePlanExerciseCommand(user_id=user_id, day_index=day_index, line_id=line_id)

    @staticmethod
    def to_list_trainer_exercises_command(
        trainer_user_id: str,
        include_archived: bool,
    ) -> ListTrainerExercisesCommand:
        return ListTrainerExercisesCommand(
            trainer_user_id=trainer_user_id,
            include_archived=include_archived,
        )

    @staticmethod
    def to_list_client_loads_command(client_user_id: str, trainer_user_id: str) -> ListClientLoadsCommand:
        return ListClientLoadsCommand(
            client_user_id=client_user_id,
            trainer_user_id=trainer_user_id,
        )

    @staticmethod
    def to_upsert_client_load_command(
        client_user_id: str,
        trainer_user_id: str,
        exercise_row_id: str,
        payload: UpsertClientLoadRequest,
    ) -> UpsertClientLoadCommand:
        return UpsertClientLoadCommand(
            client_user_id=client_user_id,
            trainer_user_id=trainer_user_id,
            exercise_row_id=exercise_row_id,
            working_weight_kg=payload.working_weight_kg,
        )

    @staticmethod
    def to_list_client_platform_loads_command(client_user_id: str) -> ListClientPlatformLoadsCommand:
        return ListClientPlatformLoadsCommand(client_user_id=client_user_id)

    @staticmethod
    def to_upsert_client_platform_load_command(
        client_user_id: str,
        exercise_row_id: str,
        payload: UpsertClientLoadRequest,
    ) -> UpsertClientPlatformLoadCommand:
        return UpsertClientPlatformLoadCommand(
            client_user_id=client_user_id,
            exercise_row_id=exercise_row_id,
            working_weight_kg=payload.working_weight_kg,
        )

    @staticmethod
    def to_add_trainer_exercise_command(
        trainer_user_id: str,
        payload: UpsertTrainerExerciseRequest,
    ) -> AddTrainerExerciseCommand:
        return AddTrainerExerciseCommand(
            trainer_user_id=trainer_user_id,
            exercise_name=payload.exercise_name,
            description=payload.description,
            equipment=payload.equipment,
            is_cardio=payload.is_cardio,
            is_hold=payload.is_hold,
            difficulty=payload.difficulty,
            workout_category=payload.workout_category,
            default_sets=payload.default_sets,
            default_reps=payload.default_reps,
            default_duration_seconds=payload.default_duration_seconds,
            default_rest_seconds=payload.default_rest_seconds,
            default_weight_kg=payload.default_weight_kg,
            load_scheme=payload.load_scheme,
            scheme_steps=list(payload.scheme_steps),
            primary_muscles=list(payload.primary_muscles),
            secondary_muscles=list(payload.secondary_muscles),
        )

    @staticmethod
    def to_update_trainer_exercise_command(
        trainer_user_id: str,
        row_id: str,
        payload: UpsertTrainerExerciseRequest,
    ) -> UpdateTrainerExerciseCommand:
        return UpdateTrainerExerciseCommand(
            trainer_user_id=trainer_user_id,
            row_id=row_id,
            exercise_name=payload.exercise_name,
            description=payload.description,
            equipment=payload.equipment,
            is_cardio=payload.is_cardio,
            is_hold=payload.is_hold,
            difficulty=payload.difficulty,
            workout_category=payload.workout_category,
            default_sets=payload.default_sets,
            default_reps=payload.default_reps,
            default_duration_seconds=payload.default_duration_seconds,
            default_rest_seconds=payload.default_rest_seconds,
            default_weight_kg=payload.default_weight_kg,
            load_scheme=payload.load_scheme,
            scheme_steps=list(payload.scheme_steps),
            primary_muscles=list(payload.primary_muscles),
            secondary_muscles=list(payload.secondary_muscles),
        )

    @staticmethod
    def to_archive_trainer_exercise_command(
        trainer_user_id: str,
        row_id: str,
    ) -> ArchiveTrainerExerciseCommand:
        return ArchiveTrainerExerciseCommand(
            trainer_user_id=trainer_user_id,
            row_id=row_id,
        )

    @staticmethod
    def to_list_platform_exercises_command(
        *,
        include_archived: bool,
        page: int,
        page_size: int,
    ) -> ListPlatformExercisesCommand:
        return ListPlatformExercisesCommand(
            include_archived=include_archived,
            page=page,
            page_size=page_size,
        )

    @staticmethod
    def to_add_platform_exercise_command(payload: UpsertPlatformExerciseRequest) -> AddPlatformExerciseCommand:
        return AddPlatformExerciseCommand(
            exercise_name=payload.exercise_name,
            description=payload.description,
            equipment=payload.equipment,
            is_cardio=payload.is_cardio,
            is_hold=payload.is_hold,
            difficulty=payload.difficulty,
            workout_category=payload.workout_category,
            default_sets=payload.default_sets,
            default_reps=payload.default_reps,
            default_duration_seconds=payload.default_duration_seconds,
            default_rest_seconds=payload.default_rest_seconds,
            default_weight_kg=payload.default_weight_kg,
            load_scheme=payload.load_scheme,
            scheme_steps=list(payload.scheme_steps),
            catalog_key=payload.catalog_key,
            primary_muscles=list(payload.primary_muscles),
            secondary_muscles=list(payload.secondary_muscles),
        )

    @staticmethod
    def to_update_platform_exercise_command(
        row_id: str,
        payload: UpsertPlatformExerciseRequest,
    ) -> UpdatePlatformExerciseCommand:
        return UpdatePlatformExerciseCommand(
            row_id=row_id,
            exercise_name=payload.exercise_name,
            description=payload.description,
            equipment=payload.equipment,
            is_cardio=payload.is_cardio,
            is_hold=payload.is_hold,
            difficulty=payload.difficulty,
            workout_category=payload.workout_category,
            default_sets=payload.default_sets,
            default_reps=payload.default_reps,
            default_duration_seconds=payload.default_duration_seconds,
            default_rest_seconds=payload.default_rest_seconds,
            default_weight_kg=payload.default_weight_kg,
            load_scheme=payload.load_scheme,
            scheme_steps=list(payload.scheme_steps),
            catalog_key=payload.catalog_key,
            primary_muscles=list(payload.primary_muscles),
            secondary_muscles=list(payload.secondary_muscles),
        )

    @staticmethod
    def to_archive_platform_exercise_command(row_id: str) -> ArchivePlatformExerciseCommand:
        return ArchivePlatformExerciseCommand(row_id=row_id)
