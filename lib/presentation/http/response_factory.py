from application.generation.policy import GenerationPolicyConfig
from domain.entities import ClientExerciseLoad, Muscle, PlanDay, PlatformExercise, TodayWorkout, TrainingPlan
from presentation.http.schemas import (
    ClientExerciseLoadResponse,
    GenerationPolicyResponse,
    MuscleResponse,
    PlanDayResponse,
    PlanExerciseResponse,
    PlatformExerciseResponse,
    SetPrescriptionResponse,
    TodayWorkoutResponse,
    TrainingPlanResponse,
)


class PlanResponseFactory:
    @staticmethod
    def from_domain_plan(plan: TrainingPlan) -> TrainingPlanResponse:
        return TrainingPlanResponse(
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
            days=[PlanResponseFactory.from_domain_day(day) for day in plan.days],
            previous_adherence=plan.previous_adherence,
        )

    @staticmethod
    def from_generation_policy(config: GenerationPolicyConfig) -> GenerationPolicyResponse:
        payload = config.to_dict()
        return GenerationPolicyResponse(
            excluded_pairs=payload["excluded_pairs"],
            default_splits=payload["default_splits"],
            default_workouts_per_week=payload["default_workouts_per_week"],
        )

    @staticmethod
    def from_domain_day(day: PlanDay) -> PlanDayResponse:
        return PlanDayResponse(
            day_id=day.day_id,
            day_index=day.day_index,
            scheduled_for=day.scheduled_for,
            week=day.week,
            day_of_week=day.day_of_week,
            volume_multiplier=day.volume_multiplier,
            is_completed=day.is_completed,
            completed_at=day.completed_at,
            exercises=[
                PlanExerciseResponse(
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
                    set_prescriptions=[
                        SetPrescriptionResponse(
                            set_index=item.set_index,
                            reps=item.reps,
                            duration_seconds=item.duration_seconds,
                            weight_kg=item.weight_kg,
                            rest_seconds=item.rest_seconds,
                        )
                        for item in line.set_prescriptions
                    ],
                )
                for line in day.exercises
            ],
        )

    @staticmethod
    def from_domain_today(workout: TodayWorkout) -> TodayWorkoutResponse:
        day = workout.day
        return TodayWorkoutResponse(
            plan_id=workout.plan_id,
            source=workout.source,
            trainer_user_id=workout.trainer_user_id,
            day_id=day.day_id,
            day_index=day.day_index,
            scheduled_for=day.scheduled_for,
            week=day.week,
            day_of_week=day.day_of_week,
            volume_multiplier=day.volume_multiplier,
            is_completed=day.is_completed,
            completed_at=day.completed_at,
            exercises=[
                PlanExerciseResponse(
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
                    set_prescriptions=[
                        SetPrescriptionResponse(
                            set_index=item.set_index,
                            reps=item.reps,
                            duration_seconds=item.duration_seconds,
                            weight_kg=item.weight_kg,
                            rest_seconds=item.rest_seconds,
                        )
                        for item in line.set_prescriptions
                    ],
                )
                for line in day.exercises
            ],
        )

    @staticmethod
    def from_domain_client_load(load: ClientExerciseLoad) -> ClientExerciseLoadResponse:
        return ClientExerciseLoadResponse(
            load_id=load.load_id,
            client_user_id=load.client_user_id,
            exercise_scope=load.exercise_scope,
            trainer_user_id=load.trainer_user_id,
            exercise_row_id=load.exercise_row_id,
            working_weight_kg=load.working_weight_kg,
            updated_at=load.updated_at,
        )

    @staticmethod
    def from_domain_platform_exercise(exercise: PlatformExercise) -> PlatformExerciseResponse:
        return PlatformExerciseResponse(
            row_id=exercise.row_id,
            catalog_key=exercise.catalog_key,
            exercise_name=exercise.exercise_name,
            description=exercise.description,
            equipment=exercise.equipment,
            is_cardio=exercise.is_cardio,
            is_hold=exercise.is_hold,
            difficulty=exercise.difficulty,
            workout_category=exercise.workout_category,  # type: ignore[arg-type]
            default_sets=exercise.default_sets,
            default_reps=exercise.default_reps,
            default_duration_seconds=exercise.default_duration_seconds,
            default_rest_seconds=exercise.default_rest_seconds,
            default_weight_kg=exercise.default_weight_kg,
            load_scheme=exercise.load_scheme,  # type: ignore[arg-type]
            scheme_steps=list(exercise.scheme_steps),
            is_active=exercise.is_active,
            video_url=exercise.video_url,
            created_at=exercise.created_at,
            updated_at=exercise.updated_at,
            primary_muscles=list(exercise.primary_muscles),
            secondary_muscles=list(exercise.secondary_muscles),
        )

    @staticmethod
    def from_domain_muscle(muscle: Muscle) -> MuscleResponse:
        return MuscleResponse(
            slug=muscle.slug,
            name_ru=muscle.name_ru,
            sort_order=muscle.sort_order,
            body_view=muscle.body_view,
            region_key=muscle.region_key,
        )
