from urllib.parse import quote, unquote

from fastapi import HTTPException, Response, status

from application.errors import IntegrationError, PlanError, ValidationError
from application.media_storage import MediaValidationError
from application.runtime import PlanApplicationRuntime
from presentation.http.error_translator import ErrorTranslator
from presentation.http.request_factory import PlanRequestFactory
from presentation.http.response_factory import PlanResponseFactory
from presentation.http.schemas import (
    ClientExerciseLoadResponse,
    ExerciseVideoUploadResponse,
    GeneratePlanRequest,
    PlanDayResponse,
    TrainerExerciseResponse,
    TrainingPlanResponse,
    UpsertClientLoadRequest,
    UpsertTrainerExerciseRequest,
)

_MEDIA_PREFIX = "/api/v1/trainers/media/"


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

    def list_client_loads(self, client_user_id: str, trainer_user_id: str) -> list[ClientExerciseLoadResponse]:
        try:
            with self._runtime.plan_service_scope() as plan_service:
                items = plan_service.list_client_loads(
                    self._request_factory.to_list_client_loads_command(client_user_id, trainer_user_id)
                )
                return [self._response_factory.from_domain_client_load(item) for item in items]
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def upsert_client_load(
        self,
        client_user_id: str,
        trainer_user_id: str,
        exercise_row_id: str,
        payload: UpsertClientLoadRequest,
    ) -> ClientExerciseLoadResponse:
        try:
            with self._runtime.plan_service_scope() as plan_service:
                item = plan_service.upsert_client_load(
                    self._request_factory.to_upsert_client_load_command(
                        client_user_id,
                        trainer_user_id,
                        exercise_row_id,
                        payload,
                    )
                )
                return self._response_factory.from_domain_client_load(item)
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def add_trainer_exercise(
        self,
        trainer_user_id: str,
        payload: UpsertTrainerExerciseRequest,
    ) -> TrainerExerciseResponse:
        try:
            with self._runtime.plan_service_scope() as plan_service:
                item = plan_service.add_trainer_exercise(
                    self._request_factory.to_add_trainer_exercise_command(trainer_user_id, payload)
                )
                return TrainerExerciseResponse.model_validate(item, from_attributes=True)
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def get_trainer_exercise(self, trainer_user_id: str, row_id: str) -> TrainerExerciseResponse:
        try:
            with self._runtime.plan_service_scope() as plan_service:
                item = plan_service.get_trainer_exercise(trainer_user_id, row_id)
                return TrainerExerciseResponse.model_validate(item, from_attributes=True)
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def update_trainer_exercise(
        self,
        trainer_user_id: str,
        row_id: str,
        payload: UpsertTrainerExerciseRequest,
    ) -> TrainerExerciseResponse:
        try:
            with self._runtime.plan_service_scope() as plan_service:
                item = plan_service.update_trainer_exercise(
                    self._request_factory.to_update_trainer_exercise_command(trainer_user_id, row_id, payload)
                )
                return TrainerExerciseResponse.model_validate(item, from_attributes=True)
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def archive_trainer_exercise(self, trainer_user_id: str, row_id: str) -> None:
        try:
            with self._runtime.plan_service_scope() as plan_service:
                plan_service.archive_trainer_exercise(
                    self._request_factory.to_archive_trainer_exercise_command(trainer_user_id, row_id)
                )
                return
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    async def upload_trainer_exercise_video(
        self,
        trainer_user_id: str,
        row_id: str,
        filename: str,
        data: bytes,
    ) -> ExerciseVideoUploadResponse:
        try:
            storage = self._runtime.video_storage
            if storage is None:
                raise IntegrationError("s3 media storage is not configured")
            object_key = await storage.upload_video(
                trainer_user_id=trainer_user_id,
                row_id=row_id,
                filename=filename,
                data=data,
            )
            video_url = f"{_MEDIA_PREFIX}{quote(object_key, safe='/')}"
            with self._runtime.plan_service_scope() as plan_service:
                _, previous_video_url = plan_service.set_trainer_exercise_video_url(
                    trainer_user_id,
                    row_id,
                    video_url,
                )
            previous_object_key = self._extract_object_key(previous_video_url)
            if previous_object_key and previous_object_key != object_key:
                try:
                    await storage.delete_media(previous_object_key)
                except PlanError:
                    pass
            return ExerciseVideoUploadResponse(
                trainer_user_id=trainer_user_id,
                row_id=row_id,
                video_url=video_url,
            )
        except MediaValidationError as exc:
            self._error_translator.raise_http_error(ValidationError(str(exc)))
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    async def delete_trainer_exercise_video(self, trainer_user_id: str, row_id: str) -> None:
        try:
            storage = self._runtime.video_storage
            with self._runtime.plan_service_scope() as plan_service:
                _, previous_video_url = plan_service.clear_trainer_exercise_video_url(trainer_user_id, row_id)
            object_key = self._extract_object_key(previous_video_url)
            if object_key and storage is not None:
                try:
                    await storage.delete_media(object_key)
                except PlanError:
                    pass
            return
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    async def get_media(self, object_key: str) -> Response:
        storage = self._runtime.video_storage
        if storage is None:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="s3 media storage is not configured")
        try:
            data, content_type = await storage.download_media(object_key)
            return Response(content=data, media_type=content_type)
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="media not found") from exc
        raise AssertionError("unreachable")

    @staticmethod
    def _extract_object_key(video_url: str | None) -> str | None:
        if not video_url:
            return None
        if video_url.startswith(_MEDIA_PREFIX):
            return unquote(video_url[len(_MEDIA_PREFIX) :])
        if video_url.startswith("videos/"):
            return video_url
        return None
