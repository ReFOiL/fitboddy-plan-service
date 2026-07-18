from __future__ import annotations

from application.models import (
    ClientExerciseLoadModel,
    PlanDayModel,
    PlatformExerciseModel,
    TrainerExerciseModel,
    TrainingPlanModel,
)
from application.repositories.serialization import (
    dumps_scheme_steps as encode_scheme_steps,
    dumps_set_prescriptions as encode_set_prescriptions,
    parse_scheme_steps,
    parse_set_prescriptions,
)
from domain.entities import (
    ClientExerciseLoad,
    PlanDay,
    PlanExercise,
    PlatformExercise,
    TrainerExercise,
    TrainingPlan,
)


class PlanMapper:
    @staticmethod
    def to_domain(plan: TrainingPlanModel) -> TrainingPlan:
        days = sorted(plan.days, key=lambda item: item.day_index)
        return TrainingPlan(
            plan_id=plan.plan_id,
            source=plan.source,
            trainer_user_id=plan.trainer_user_id,
            user_id=plan.user_id,
            status=plan.status,
            goal=plan.goal,
            level=plan.level,
            workouts_per_week=plan.workouts_per_week,
            start_date=plan.start_date,
            end_date=plan.end_date,
            created_at=plan.created_at,
            updated_at=plan.updated_at,
            days=[PlanMapper.day_to_domain(day) for day in days],
        )

    @staticmethod
    def day_to_domain(day: PlanDayModel) -> PlanDay:
        exercises = sorted(day.exercises, key=lambda item: item.sort_order)
        return PlanDay(
            day_id=day.day_id,
            day_index=day.day_index,
            scheduled_for=day.scheduled_for,
            week=day.week,
            day_of_week=day.day_of_week,
            volume_multiplier=day.volume_multiplier,
            is_completed=bool(day.is_completed),
            completed_at=day.completed_at,
            exercises=[
                PlanExercise(
                    line_id=line.line_id,
                    exercise_id=line.exercise_id,
                    exercise_name=line.exercise_name,
                    category=line.category,
                    is_cardio=line.is_cardio,
                    sort_order=line.sort_order,
                    sets=line.sets,
                    reps=line.reps,
                    duration_seconds=line.duration_seconds,
                    rest_seconds=line.rest_seconds,
                    weight_kg=line.weight_kg,
                    set_prescriptions=parse_set_prescriptions(line.set_prescriptions_json),
                )
                for line in exercises
            ],
        )

    @staticmethod
    def _muscle_lists_from_links(links: list) -> tuple[list[str], list[str]]:
        primary_rows = sorted(
            (link for link in links if getattr(link, "role", None) == "primary"),
            key=lambda item: item.position,
        )
        secondary_rows = sorted(
            (link for link in links if getattr(link, "role", None) == "secondary"),
            key=lambda item: item.position,
        )
        return (
            [item.muscle_slug for item in primary_rows],
            [item.muscle_slug for item in secondary_rows],
        )

    @staticmethod
    def trainer_exercise_to_domain(exercise: TrainerExerciseModel) -> TrainerExercise:
        primary, secondary = PlanMapper._muscle_lists_from_links(list(exercise.muscle_links or []))
        return TrainerExercise(
            row_id=exercise.row_id,
            trainer_user_id=exercise.trainer_user_id,
            exercise_name=exercise.exercise_name,
            description=exercise.description,
            equipment=exercise.equipment,
            is_cardio=exercise.is_cardio,
            is_hold=exercise.is_hold,
            difficulty=exercise.difficulty,
            workout_category=exercise.workout_category,
            default_sets=exercise.default_sets,
            default_reps=exercise.default_reps,
            default_duration_seconds=exercise.default_duration_seconds,
            default_rest_seconds=exercise.default_rest_seconds,
            default_weight_kg=exercise.default_weight_kg,
            load_scheme=exercise.load_scheme or "flat",
            scheme_steps=parse_scheme_steps(exercise.scheme_steps_json),
            is_active=exercise.is_active,
            video_url=exercise.video_url,
            created_at=exercise.created_at,
            updated_at=exercise.updated_at,
            primary_muscles=primary,
            secondary_muscles=secondary,
        )

    @staticmethod
    def platform_exercise_to_domain(exercise: PlatformExerciseModel) -> PlatformExercise:
        primary, secondary = PlanMapper._muscle_lists_from_links(list(exercise.muscle_links or []))
        return PlatformExercise(
            row_id=exercise.row_id,
            catalog_key=exercise.catalog_key,
            exercise_name=exercise.exercise_name,
            description=exercise.description,
            equipment=exercise.equipment,
            is_cardio=exercise.is_cardio,
            is_hold=exercise.is_hold,
            difficulty=exercise.difficulty,
            workout_category=exercise.workout_category,
            default_sets=exercise.default_sets,
            default_reps=exercise.default_reps,
            default_duration_seconds=exercise.default_duration_seconds,
            default_rest_seconds=exercise.default_rest_seconds,
            default_weight_kg=exercise.default_weight_kg,
            load_scheme=exercise.load_scheme or "flat",
            scheme_steps=parse_scheme_steps(exercise.scheme_steps_json),
            is_active=exercise.is_active,
            video_url=exercise.video_url,
            created_at=exercise.created_at,
            updated_at=exercise.updated_at,
            primary_muscles=primary,
            secondary_muscles=secondary,
        )

    @staticmethod
    def client_load_to_domain(model: ClientExerciseLoadModel) -> ClientExerciseLoad:
        return ClientExerciseLoad(
            load_id=model.load_id,
            client_user_id=model.client_user_id,
            exercise_scope=model.exercise_scope,
            trainer_user_id=model.trainer_user_id,
            exercise_row_id=model.exercise_row_id,
            working_weight_kg=model.working_weight_kg,
            updated_at=model.updated_at,
        )

    @staticmethod
    def dumps_set_prescriptions(prescriptions: list | tuple) -> str | None:
        return encode_set_prescriptions(prescriptions)

    @staticmethod
    def dumps_scheme_steps(steps: list[float]) -> str | None:
        return encode_scheme_steps(steps)
