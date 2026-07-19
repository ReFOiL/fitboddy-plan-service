from urllib.parse import quote, unquote

from fastapi import HTTPException, Response, status

from application.errors import ForbiddenError, IntegrationError, PlanError, UnauthorizedError, ValidationError
from application.gateways import AuthUser
from application.generation.policy import GenerationPolicyConfig
from application.media_storage import MediaValidationError
from application.runtime import PlanApplicationRuntime
from presentation.http.error_translator import ErrorTranslator
from presentation.http.request_factory import PlanRequestFactory
from presentation.http.response_factory import PlanResponseFactory
from presentation.http.schemas import (
    AdminExerciseListResponse,
    AdminPlatformExerciseListResponse,
    ClientExerciseLoadResponse,
    ExerciseVideoUploadResponse,
    GeneratePlanRequest,
    GenerationPolicyResponse,
    MuscleResponse,
    PlanDayResponse,
    PlatformExerciseResponse,
    PlatformExerciseVideoUploadResponse,
    TodayWorkoutResponse,
    TrainerExerciseResponse,
    TrainingPlanResponse,
    UpsertClientLoadRequest,
    UpsertGenerationPolicyRequest,
    UpsertPlatformExerciseRequest,
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

    def list_muscles(self) -> list[MuscleResponse]:
        try:
            with self._runtime.plan_service_scope() as plan_service:
                items = plan_service.list_muscles()
                return [self._response_factory.from_domain_muscle(item) for item in items]
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def ready(self) -> dict[str, str]:
        self._runtime.check_ready()
        return {"status": "ready"}

    def generate_plan(self, *, authorization: str | None, payload: GeneratePlanRequest) -> TrainingPlanResponse:
        try:
            self._require_generate_access(authorization, payload)
            with self._runtime.plan_service_scope() as plan_service:
                plan = plan_service.generate_plan(self._request_factory.to_generate_command(payload))
                return self._response_factory.from_domain_plan(plan)
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def get_active_plan(self, *, authorization: str | None, user_id: str) -> TrainingPlanResponse:
        try:
            self._require_can_access_client_plan(authorization, user_id)
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

    def get_today_workout(self, *, authorization: str | None) -> TodayWorkoutResponse:
        try:
            user = self._require_current_user(authorization)
            with self._runtime.plan_service_scope() as plan_service:
                workout = plan_service.get_today_workout(self._request_factory.to_get_today_command(user.user_id))
                return self._response_factory.from_domain_today(workout)
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def complete_plan_day(self, *, authorization: str | None, day_index: int) -> TodayWorkoutResponse:
        try:
            user = self._require_current_user(authorization)
            with self._runtime.plan_service_scope() as plan_service:
                workout = plan_service.complete_plan_day(
                    self._request_factory.to_complete_day_command(user.user_id, day_index)
                )
                return self._response_factory.from_domain_today(workout)
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def replace_plan_exercise(
        self,
        *,
        authorization: str | None,
        day_index: int,
        line_id: str,
    ) -> TodayWorkoutResponse:
        try:
            user = self._require_current_user(authorization)
            with self._runtime.plan_service_scope() as plan_service:
                workout = plan_service.replace_plan_exercise(
                    self._request_factory.to_replace_exercise_command(user.user_id, day_index, line_id)
                )
                return self._response_factory.from_domain_today(workout)
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

    def list_client_loads(
        self,
        *,
        authorization: str | None,
        client_user_id: str,
        trainer_user_id: str,
    ) -> list[ClientExerciseLoadResponse]:
        try:
            self._require_trainer_client_relation(authorization, client_user_id, trainer_user_id)
            with self._runtime.plan_service_scope() as plan_service:
                items = plan_service.list_client_loads(
                    self._request_factory.to_list_client_loads_command(client_user_id, trainer_user_id)
                )
                return [self._response_factory.from_domain_client_load(item) for item in items]
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def list_client_platform_loads(
        self,
        *,
        authorization: str | None,
        client_user_id: str,
    ) -> list[ClientExerciseLoadResponse]:
        try:
            self._require_self_client(authorization, client_user_id)
            with self._runtime.plan_service_scope() as plan_service:
                items = plan_service.list_client_platform_loads(
                    self._request_factory.to_list_client_platform_loads_command(client_user_id)
                )
                return [self._response_factory.from_domain_client_load(item) for item in items]
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def upsert_client_load(
        self,
        *,
        authorization: str | None,
        client_user_id: str,
        trainer_user_id: str,
        exercise_row_id: str,
        payload: UpsertClientLoadRequest,
    ) -> ClientExerciseLoadResponse:
        try:
            self._require_trainer_client_relation(authorization, client_user_id, trainer_user_id)
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

    def upsert_client_platform_load(
        self,
        *,
        authorization: str | None,
        client_user_id: str,
        exercise_row_id: str,
        payload: UpsertClientLoadRequest,
    ) -> ClientExerciseLoadResponse:
        try:
            self._require_self_client(authorization, client_user_id)
            with self._runtime.plan_service_scope() as plan_service:
                item = plan_service.upsert_client_platform_load(
                    self._request_factory.to_upsert_client_platform_load_command(
                        client_user_id,
                        exercise_row_id,
                        payload,
                    )
                )
                return self._response_factory.from_domain_client_load(item)
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def list_active_platform_exercises(self) -> list[PlatformExerciseResponse]:
        try:
            with self._runtime.plan_service_scope() as plan_service:
                items = plan_service.list_active_platform_exercises()
                return [self._response_factory.from_domain_platform_exercise(item) for item in items]
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def get_active_platform_exercise(self, row_id: str) -> PlatformExerciseResponse:
        try:
            with self._runtime.plan_service_scope() as plan_service:
                item = plan_service.get_active_platform_exercise(row_id)
                return self._response_factory.from_domain_platform_exercise(item)
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
                owner_id=trainer_user_id,
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

    def admin_list_exercises(
        self,
        *,
        authorization: str | None,
        trainer_user_id: str | None,
        include_archived: bool,
        page: int,
        page_size: int,
    ) -> AdminExerciseListResponse:
        try:
            self._require_platform_admin(authorization)
            with self._runtime.plan_service_scope() as plan_service:
                items, total = plan_service.admin_list_exercises(
                    trainer_user_id=trainer_user_id,
                    include_archived=include_archived,
                    page=page,
                    page_size=page_size,
                )
                return AdminExerciseListResponse(
                    items=[TrainerExerciseResponse.model_validate(item, from_attributes=True) for item in items],
                    total=total,
                    page=page,
                    page_size=page_size,
                )
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def admin_list_platform_exercises(
        self,
        *,
        authorization: str | None,
        include_archived: bool,
        page: int,
        page_size: int,
    ) -> AdminPlatformExerciseListResponse:
        try:
            self._require_platform_admin(authorization)
            with self._runtime.plan_service_scope() as plan_service:
                items, total = plan_service.list_platform_exercises(
                    self._request_factory.to_list_platform_exercises_command(
                        include_archived=include_archived,
                        page=page,
                        page_size=page_size,
                    )
                )
                return AdminPlatformExerciseListResponse(
                    items=[self._response_factory.from_domain_platform_exercise(item) for item in items],
                    total=total,
                    page=page,
                    page_size=page_size,
                )
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def admin_create_platform_exercise(
        self,
        *,
        authorization: str | None,
        payload: UpsertPlatformExerciseRequest,
    ) -> PlatformExerciseResponse:
        try:
            self._require_platform_admin(authorization)
            with self._runtime.plan_service_scope() as plan_service:
                item = plan_service.add_platform_exercise(
                    self._request_factory.to_add_platform_exercise_command(payload)
                )
                return self._response_factory.from_domain_platform_exercise(item)
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def admin_get_platform_exercise(
        self,
        *,
        authorization: str | None,
        row_id: str,
    ) -> PlatformExerciseResponse:
        try:
            self._require_platform_admin(authorization)
            with self._runtime.plan_service_scope() as plan_service:
                item = plan_service.get_platform_exercise(row_id)
                return self._response_factory.from_domain_platform_exercise(item)
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def admin_update_platform_exercise(
        self,
        *,
        authorization: str | None,
        row_id: str,
        payload: UpsertPlatformExerciseRequest,
    ) -> PlatformExerciseResponse:
        try:
            self._require_platform_admin(authorization)
            with self._runtime.plan_service_scope() as plan_service:
                item = plan_service.update_platform_exercise(
                    self._request_factory.to_update_platform_exercise_command(row_id, payload)
                )
                return self._response_factory.from_domain_platform_exercise(item)
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def admin_archive_platform_exercise(self, *, authorization: str | None, row_id: str) -> None:
        try:
            self._require_platform_admin(authorization)
            with self._runtime.plan_service_scope() as plan_service:
                plan_service.archive_platform_exercise(
                    self._request_factory.to_archive_platform_exercise_command(row_id)
                )
                return
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    async def admin_upload_platform_exercise_video(
        self,
        *,
        authorization: str | None,
        row_id: str,
        filename: str,
        data: bytes,
    ) -> PlatformExerciseVideoUploadResponse:
        try:
            self._require_platform_admin(authorization)
            storage = self._runtime.video_storage
            if storage is None:
                raise IntegrationError("s3 media storage is not configured")
            object_key = await storage.upload_video(
                owner_id="platform",
                row_id=row_id,
                filename=filename,
                data=data,
            )
            video_url = f"{_MEDIA_PREFIX}{quote(object_key, safe='/')}"
            with self._runtime.plan_service_scope() as plan_service:
                _, previous_video_url = plan_service.set_platform_exercise_video_url(row_id, video_url)
            previous_object_key = self._extract_object_key(previous_video_url)
            if previous_object_key and previous_object_key != object_key:
                try:
                    await storage.delete_media(previous_object_key)
                except PlanError:
                    pass
            return PlatformExerciseVideoUploadResponse(row_id=row_id, video_url=video_url)
        except MediaValidationError as exc:
            self._error_translator.raise_http_error(ValidationError(str(exc)))
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    async def admin_delete_platform_exercise_video(self, *, authorization: str | None, row_id: str) -> None:
        try:
            self._require_platform_admin(authorization)
            storage = self._runtime.video_storage
            with self._runtime.plan_service_scope() as plan_service:
                _, previous_video_url = plan_service.clear_platform_exercise_video_url(row_id)
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

    def admin_archive_exercise(self, *, authorization: str | None, trainer_user_id: str, row_id: str) -> None:
        try:
            self._require_platform_admin(authorization)
            with self._runtime.plan_service_scope() as plan_service:
                plan_service.archive_trainer_exercise(
                    self._request_factory.to_archive_trainer_exercise_command(trainer_user_id, row_id)
                )
                return
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def admin_get_generation_policy(self, *, authorization: str | None) -> GenerationPolicyResponse:
        try:
            self._require_platform_admin(authorization)
            with self._runtime.plan_service_scope() as plan_service:
                config = plan_service.get_generation_policy()
                return self._response_factory.from_generation_policy(config)
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def admin_upsert_generation_policy(
        self,
        *,
        authorization: str | None,
        payload: UpsertGenerationPolicyRequest,
    ) -> GenerationPolicyResponse:
        try:
            self._require_platform_admin(authorization)
            config = GenerationPolicyConfig.from_dict(payload.model_dump())
            with self._runtime.plan_service_scope() as plan_service:
                saved = plan_service.upsert_generation_policy(config)
                return self._response_factory.from_generation_policy(saved)
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def admin_get_active_plan(self, *, authorization: str | None, user_id: str) -> TrainingPlanResponse:
        try:
            self._require_platform_admin(authorization)
            with self._runtime.plan_service_scope() as plan_service:
                plan = plan_service.admin_get_active_plan(user_id)
                return self._response_factory.from_domain_plan(plan)
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def admin_list_client_loads(
        self,
        *,
        authorization: str | None,
        client_user_id: str,
        trainer_user_id: str,
    ) -> list[ClientExerciseLoadResponse]:
        try:
            self._require_platform_admin(authorization)
            with self._runtime.plan_service_scope() as plan_service:
                loads = plan_service.admin_list_client_loads(client_user_id, trainer_user_id)
                return [self._response_factory.from_domain_client_load(item) for item in loads]
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def _require_current_user(self, authorization: str | None) -> AuthUser:
        token = self._extract_bearer_token(authorization)
        return self._runtime.auth_gateway.get_current_user(token)

    def _require_platform_admin(self, authorization: str | None) -> None:
        token = self._extract_bearer_token(authorization)
        self._runtime.auth_gateway.require_platform_admin(token)

    def _require_self_client(self, authorization: str | None, client_user_id: str) -> AuthUser:
        user = self._require_current_user(authorization)
        if user.user_id != client_user_id:
            raise ForbiddenError("not allowed to access another client's platform loads")
        return user

    def _require_can_access_client_plan(self, authorization: str | None, client_user_id: str) -> AuthUser:
        user = self._require_current_user(authorization)
        if user.user_id == client_user_id:
            return user
        active_trainer_id = self._runtime.tenant_gateway.get_client_active_trainer_id(client_user_id)
        if active_trainer_id is not None and user.user_id == active_trainer_id:
            return user
        raise ForbiddenError("not allowed to access this client's plan")

    def _require_trainer_client_relation(
        self,
        authorization: str | None,
        client_user_id: str,
        trainer_user_id: str,
    ) -> AuthUser:
        user = self._require_current_user(authorization)
        if user.user_id not in {client_user_id, trainer_user_id}:
            raise ForbiddenError("not allowed to access these client loads")
        active_trainer_id = self._runtime.tenant_gateway.get_client_active_trainer_id(client_user_id)
        if active_trainer_id != trainer_user_id:
            raise ForbiddenError("active trainer-client relation required")
        return user

    def _require_generate_access(self, authorization: str | None, payload: GeneratePlanRequest) -> AuthUser:
        user = self._require_current_user(authorization)
        source = (payload.source or "trainer").strip().lower()
        if source == "system":
            if user.user_id != payload.user_id:
                raise ForbiddenError("system plan can only be generated for self")
            return user
        trainer_user_id = (payload.trainer_user_id or "").strip()
        if not trainer_user_id:
            raise ValidationError("trainer_user_id is required when source=trainer")
        if user.user_id not in {payload.user_id, trainer_user_id}:
            raise ForbiddenError("not allowed to generate plan for this client")
        active_trainer_id = self._runtime.tenant_gateway.get_client_active_trainer_id(payload.user_id)
        if active_trainer_id != trainer_user_id:
            raise ForbiddenError("active trainer-client relation required")
        return user

    @staticmethod
    def _extract_bearer_token(authorization: str | None) -> str:
        if authorization is None or not authorization.startswith("Bearer "):
            raise UnauthorizedError("missing bearer token")
        token = authorization.removeprefix("Bearer ").strip()
        if not token:
            raise UnauthorizedError("empty bearer token")
        return token

    @staticmethod
    def _extract_object_key(video_url: str | None) -> str | None:
        if not video_url:
            return None
        if video_url.startswith(_MEDIA_PREFIX):
            return unquote(video_url[len(_MEDIA_PREFIX) :])
        if video_url.startswith("videos/"):
            return video_url
        return None
