from domain.entities import ClientExerciseLoad, PlanDay, TrainingPlan
from presentation.http.schemas import (
    ClientExerciseLoadResponse,
    PlanDayResponse,
    PlanExerciseResponse,
    SetPrescriptionResponse,
    TrainingPlanResponse,
)


class PlanResponseFactory:
    @staticmethod
    def from_domain_plan(plan: TrainingPlan) -> TrainingPlanResponse:
        return TrainingPlanResponse(
            plan_id=plan.plan_id,
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
            trainer_user_id=load.trainer_user_id,
            exercise_row_id=load.exercise_row_id,
            working_weight_kg=load.working_weight_kg,
            updated_at=load.updated_at,
        )
