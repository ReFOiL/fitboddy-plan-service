from application.commands import (
    AddTrainerExerciseCommand,
    ArchiveTrainerExerciseCommand,
    GeneratePlanCommand,
    GetActivePlanCommand,
    GetPlanDayCommand,
    ListTrainerExercisesCommand,
    UpdateTrainerExerciseCommand,
)
from presentation.http.schemas import GeneratePlanRequest, UpsertTrainerExerciseRequest


class PlanRequestFactory:
    @staticmethod
    def to_generate_command(payload: GeneratePlanRequest) -> GeneratePlanCommand:
        return GeneratePlanCommand(
            trainer_user_id=payload.trainer_user_id,
            user_id=payload.user_id,
            goal=payload.goal,
            level=payload.level,
            workout_location=payload.workout_location,
            workouts_per_week=payload.workouts_per_week,
            equipment=payload.equipment,
            start_date=payload.start_date,
        )

    @staticmethod
    def to_get_active_command(user_id: str) -> GetActivePlanCommand:
        return GetActivePlanCommand(user_id=user_id)

    @staticmethod
    def to_get_day_command(plan_id: str, day_index: int) -> GetPlanDayCommand:
        return GetPlanDayCommand(plan_id=plan_id, day_index=day_index)

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
            difficulty=payload.difficulty,
            workout_category=payload.workout_category,
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
            difficulty=payload.difficulty,
            workout_category=payload.workout_category,
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
