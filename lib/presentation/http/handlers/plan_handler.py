from application.errors import PlanError
from application.runtime import PlanApplicationRuntime
from presentation.http.error_translator import ErrorTranslator
from presentation.http.request_factory import PlanRequestFactory
from presentation.http.response_factory import PlanResponseFactory
from presentation.http.schemas import (
    GeneratePlanRequest,
    PlanDayResponse,
    TrainerExerciseResponse,
    TrainingPlanResponse,
    UpsertTrainerExerciseRequest,
)


class PlanHttpHandler:
    def __init__(
        self,
        runtime: PlanApplicationRuntime,
        request_factory: PlanRequestFactory,
        response_factory: PlanResponseFactory,
        error_translator: ErrorTranslator,
    ) -> None:
        self._runtime = runtime
        self._request_factory = request_factory
        self._response_factory = response_factory
        self._error_translator = error_translator

    def health(self) -> dict[str, str]:
        return {"status": "ok"}

    def ready(self) -> dict[str, str]:
        self._runtime.check_ready()
        return {"status": "ready"}

    def generate_plan(self, payload: GeneratePlanRequest) -> TrainingPlanResponse:
        try:
            with self._runtime.plan_service_scope() as plan_service:
                plan = plan_service.generate_plan(self._request_factory.to_generate_command(payload))
                return self._response_factory.from_domain_plan(plan)
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def get_active_plan(self, user_id: str) -> TrainingPlanResponse:
        try:
            with self._runtime.plan_service_scope() as plan_service:
                plan = plan_service.get_active_plan(self._request_factory.to_get_active_command(user_id))
                return self._response_factory.from_domain_plan(plan)
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def get_plan_day(self, plan_id: str, day_index: int) -> PlanDayResponse:
        try:
            with self._runtime.plan_service_scope() as plan_service:
                day = plan_service.get_plan_day(self._request_factory.to_get_day_command(plan_id, day_index))
                return self._response_factory.from_domain_day(day)
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def list_trainer_exercises(self, trainer_user_id: str, include_archived: bool) -> list[TrainerExerciseResponse]:
        try:
            with self._runtime.plan_service_scope() as plan_service:
                items = plan_service.list_trainer_exercises(
                    self._request_factory.to_list_trainer_exercises_command(trainer_user_id, include_archived)
                )
                return [TrainerExerciseResponse.model_validate(item, from_attributes=True) for item in items]
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def add_trainer_exercise(
        self,
        trainer_user_id: str,
        exercise_id: str,
        payload: UpsertTrainerExerciseRequest,
    ) -> TrainerExerciseResponse:
        try:
            with self._runtime.plan_service_scope() as plan_service:
                item = plan_service.add_trainer_exercise(
                    self._request_factory.to_add_trainer_exercise_command(trainer_user_id, exercise_id, payload)
                )
                return TrainerExerciseResponse.model_validate(item, from_attributes=True)
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def update_trainer_exercise(
        self,
        trainer_user_id: str,
        exercise_id: str,
        payload: UpsertTrainerExerciseRequest,
    ) -> TrainerExerciseResponse:
        try:
            with self._runtime.plan_service_scope() as plan_service:
                item = plan_service.update_trainer_exercise(
                    self._request_factory.to_update_trainer_exercise_command(trainer_user_id, exercise_id, payload)
                )
                return TrainerExerciseResponse.model_validate(item, from_attributes=True)
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def archive_trainer_exercise(self, trainer_user_id: str, exercise_id: str) -> None:
        try:
            with self._runtime.plan_service_scope() as plan_service:
                plan_service.archive_trainer_exercise(
                    self._request_factory.to_archive_trainer_exercise_command(trainer_user_id, exercise_id)
                )
                return
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")
