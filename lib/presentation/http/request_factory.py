from application.commands import (
    AddPlanDayCommand,
    AddPlanSlotCommand,
    AddPlatformExerciseCommand,
    AddTrainerExerciseCommand,
    ArchivePlatformExerciseCommand,
    ArchiveTrainerExerciseCommand,
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
    RestoreTrainerExerciseCommand,
    UpdatePlanDayCommand,
    UpdatePlanSlotCommand,
    UpdatePlatformExerciseCommand,
    UpdateTrainerExerciseCommand,
    UpsertClientLoadCommand,
    UpsertClientPlatformLoadCommand,
)
from presentation.http.schemas import (
    AddPlanDayRequest,
    CompletePlanDayRequest,
    CopyPlanDayRequest,
    CopyPlanWeekRequest,
    CreateEmptyPlanRequest,
    GeneratePlanRequest,
    PlanSlotWriteRequest,
    ReplacePlanDayRequest,
    ReorderPlanSlotsRequest,
    UpdatePlanDayRequest,
    UpdatePlanSlotRequest,
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
    def to_get_trainer_client_plan_command(
        client_user_id: str,
        trainer_user_id: str,
    ) -> GetTrainerClientPlanCommand:
        return GetTrainerClientPlanCommand(
            client_user_id=client_user_id,
            trainer_user_id=trainer_user_id,
        )

    @staticmethod
    def to_create_empty_plan_command(
        client_user_id: str,
        trainer_user_id: str,
        payload: CreateEmptyPlanRequest,
    ) -> CreateEmptyPlanCommand:
        return CreateEmptyPlanCommand(
            client_user_id=client_user_id,
            trainer_user_id=trainer_user_id,
            goal=payload.goal,
            level=payload.level,
            workouts_per_week=payload.workouts_per_week,
            start_date=payload.start_date,
            day_count=payload.day_count,
        )

    @staticmethod
    def to_replace_plan_day_command(
        client_user_id: str,
        trainer_user_id: str,
        day_index: int,
        payload: ReplacePlanDayRequest,
    ) -> ReplacePlanDaySlotsCommand:
        return ReplacePlanDaySlotsCommand(
            client_user_id=client_user_id,
            trainer_user_id=trainer_user_id,
            day_index=day_index,
            slots=tuple(PlanRequestFactory._to_slot_input(slot) for slot in payload.slots),
        )

    @staticmethod
    def to_add_plan_slot_command(
        client_user_id: str,
        trainer_user_id: str,
        day_index: int,
        payload: PlanSlotWriteRequest,
    ) -> AddPlanSlotCommand:
        return AddPlanSlotCommand(
            client_user_id=client_user_id,
            trainer_user_id=trainer_user_id,
            day_index=day_index,
            slot=PlanRequestFactory._to_slot_input(payload),
        )

    @staticmethod
    def to_update_plan_slot_command(
        client_user_id: str,
        trainer_user_id: str,
        day_index: int,
        line_id: str,
        payload: UpdatePlanSlotRequest,
    ) -> UpdatePlanSlotCommand:
        specified = payload.model_fields_set
        return UpdatePlanSlotCommand(
            client_user_id=client_user_id,
            trainer_user_id=trainer_user_id,
            day_index=day_index,
            line_id=line_id,
            sets=payload.sets,
            sets_specified="sets" in specified,
            reps=payload.reps,
            reps_specified="reps" in specified,
            duration_seconds=payload.duration_seconds,
            duration_specified="duration_seconds" in specified,
            rest_seconds=payload.rest_seconds,
            rest_specified="rest_seconds" in specified,
            weight_kg=payload.weight_kg,
            weight_specified="weight_kg" in specified,
            note=payload.note,
            note_specified="note" in specified,
        )

    @staticmethod
    def to_delete_plan_slot_command(
        client_user_id: str,
        trainer_user_id: str,
        day_index: int,
        line_id: str,
    ) -> DeletePlanSlotCommand:
        return DeletePlanSlotCommand(
            client_user_id=client_user_id,
            trainer_user_id=trainer_user_id,
            day_index=day_index,
            line_id=line_id,
        )

    @staticmethod
    def to_reorder_plan_slots_command(
        client_user_id: str,
        trainer_user_id: str,
        day_index: int,
        payload: ReorderPlanSlotsRequest,
    ) -> ReorderPlanSlotsCommand:
        return ReorderPlanSlotsCommand(
            client_user_id=client_user_id,
            trainer_user_id=trainer_user_id,
            day_index=day_index,
            line_ids=tuple(payload.line_ids),
        )

    @staticmethod
    def _to_slot_input(payload: PlanSlotWriteRequest) -> PlanSlotInput:
        specified = payload.model_fields_set
        return PlanSlotInput(
            exercise_id=payload.exercise_id.strip(),
            sets=payload.sets,
            sets_specified="sets" in specified,
            reps=payload.reps,
            reps_specified="reps" in specified,
            duration_seconds=payload.duration_seconds,
            duration_specified="duration_seconds" in specified,
            rest_seconds=payload.rest_seconds,
            rest_specified="rest_seconds" in specified,
            weight_kg=payload.weight_kg,
            weight_specified="weight_kg" in specified,
            note=payload.note,
        )

    @staticmethod
    def to_add_plan_day_command(
        client_user_id: str,
        trainer_user_id: str,
        payload: AddPlanDayRequest,
    ) -> AddPlanDayCommand:
        return AddPlanDayCommand(
            client_user_id=client_user_id,
            trainer_user_id=trainer_user_id,
            week=payload.week,
            day_of_week=payload.day_of_week,
            scheduled_time=payload.scheduled_time,
        )

    @staticmethod
    def to_remove_plan_day_command(
        client_user_id: str,
        trainer_user_id: str,
        day_index: int,
    ) -> RemovePlanDayCommand:
        return RemovePlanDayCommand(
            client_user_id=client_user_id,
            trainer_user_id=trainer_user_id,
            day_index=day_index,
        )

    @staticmethod
    def to_update_plan_day_command(
        client_user_id: str,
        trainer_user_id: str,
        day_index: int,
        payload: UpdatePlanDayRequest,
    ) -> UpdatePlanDayCommand:
        return UpdatePlanDayCommand(
            client_user_id=client_user_id,
            trainer_user_id=trainer_user_id,
            day_index=day_index,
            scheduled_time=payload.scheduled_time,
            scheduled_time_specified="scheduled_time" in payload.model_fields_set,
        )

    @staticmethod
    def to_copy_plan_day_command(
        client_user_id: str,
        trainer_user_id: str,
        day_index: int,
        payload: CopyPlanDayRequest,
    ) -> CopyPlanDayCommand:
        return CopyPlanDayCommand(
            client_user_id=client_user_id,
            trainer_user_id=trainer_user_id,
            day_index=day_index,
            week=payload.week,
            day_of_week=payload.day_of_week,
            mode=payload.mode,
        )

    @staticmethod
    def to_copy_plan_week_command(
        client_user_id: str,
        trainer_user_id: str,
        week: int,
        payload: CopyPlanWeekRequest,
    ) -> CopyPlanWeekCommand:
        return CopyPlanWeekCommand(
            client_user_id=client_user_id,
            trainer_user_id=trainer_user_id,
            week=week,
            target_week=payload.target_week,
            mode=payload.mode,
        )

    @staticmethod
    def to_get_day_command(plan_id: str, day_index: int) -> GetPlanDayCommand:
        return GetPlanDayCommand(plan_id=plan_id, day_index=day_index)

    @staticmethod
    def to_get_today_command(user_id: str) -> GetTodayWorkoutCommand:
        return GetTodayWorkoutCommand(user_id=user_id)

    @staticmethod
    def to_complete_day_command(
        user_id: str,
        day_index: int,
        payload: CompletePlanDayRequest | None,
    ) -> CompletePlanDayCommand:
        return CompletePlanDayCommand(
            user_id=user_id,
            day_index=day_index,
            started_at=None if payload is None else payload.started_at,
        )

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
    def to_restore_trainer_exercise_command(
        trainer_user_id: str,
        row_id: str,
    ) -> RestoreTrainerExerciseCommand:
        return RestoreTrainerExerciseCommand(
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
