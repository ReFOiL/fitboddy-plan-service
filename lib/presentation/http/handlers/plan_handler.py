import hashlib
import logging
import time

from fastapi import HTTPException, Response, status
from fastapi.responses import StreamingResponse

from application.errors import ForbiddenError, IntegrationError, PlanError, UnauthorizedError, ValidationError
from application.gateways import AuthUser
from application.generation.policy import GenerationPolicyConfig
from application.media_keys import (
    PLATFORM_MEDIA_OWNER,
    etag_matches,
    is_internal_media_key,
    is_safe_object_key,
    media_key_owned_by,
    normalize_stored_media,
)
from application.media_storage import MediaValidationError, OpenedMedia, validate_photo_bytes
from application.media_urls import MediaUrlSigner
from application.runtime import PlanApplicationRuntime
from domain.entities import PlatformExercise, TrainerExercise
from presentation.http.error_translator import ErrorTranslator
from presentation.http.request_factory import PlanRequestFactory
from presentation.http.response_factory import PlanResponseFactory
from presentation.http.schemas import (
    AdminExerciseListResponse,
    AdminPlatformExerciseListResponse,
    ClientExerciseLoadResponse,
    ExercisePhotoUploadResponse,
    ExerciseVideoUploadResponse,
    GeneratePlanRequest,
    GenerationPolicyResponse,
    MuscleResponse,
    PlanDayResponse,
    PlatformExercisePhotoUploadResponse,
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

logger = logging.getLogger(__name__)


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

    def get_plan_day(self, *, authorization: str | None, plan_id: str, day_index: int) -> PlanDayResponse:
        try:
            with self._runtime.plan_service_scope() as plan_service:
                plan = plan_service.require_plan(plan_id)
                self._require_can_access_client_plan(authorization, plan.user_id)
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

    def list_trainer_exercises(
        self,
        *,
        authorization: str | None,
        trainer_user_id: str,
        include_archived: bool,
    ) -> list[TrainerExerciseResponse]:
        try:
            self._require_self_trainer(authorization, trainer_user_id)
            with self._runtime.plan_service_scope() as plan_service:
                items = plan_service.list_trainer_exercises(
                    self._request_factory.to_list_trainer_exercises_command(trainer_user_id, include_archived)
                )
                return [self._trainer_exercise_response(item) for item in items]
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
                return [self._platform_exercise_response(item) for item in items]
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def get_active_platform_exercise(self, row_id: str) -> PlatformExerciseResponse:
        try:
            with self._runtime.plan_service_scope() as plan_service:
                item = plan_service.get_active_platform_exercise(row_id)
                return self._platform_exercise_response(item)
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def add_trainer_exercise(
        self,
        *,
        authorization: str | None,
        trainer_user_id: str,
        payload: UpsertTrainerExerciseRequest,
    ) -> TrainerExerciseResponse:
        try:
            self._require_self_trainer(authorization, trainer_user_id)
            with self._runtime.plan_service_scope() as plan_service:
                item = plan_service.add_trainer_exercise(
                    self._request_factory.to_add_trainer_exercise_command(trainer_user_id, payload)
                )
                return self._trainer_exercise_response(item)
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def get_trainer_exercise(
        self,
        *,
        authorization: str | None,
        trainer_user_id: str,
        row_id: str,
    ) -> TrainerExerciseResponse:
        try:
            self._require_self_trainer(authorization, trainer_user_id)
            with self._runtime.plan_service_scope() as plan_service:
                item = plan_service.get_trainer_exercise(trainer_user_id, row_id)
                return self._trainer_exercise_response(item)
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def update_trainer_exercise(
        self,
        *,
        authorization: str | None,
        trainer_user_id: str,
        row_id: str,
        payload: UpsertTrainerExerciseRequest,
    ) -> TrainerExerciseResponse:
        try:
            self._require_self_trainer(authorization, trainer_user_id)
            with self._runtime.plan_service_scope() as plan_service:
                item = plan_service.update_trainer_exercise(
                    self._request_factory.to_update_trainer_exercise_command(trainer_user_id, row_id, payload)
                )
                return self._trainer_exercise_response(item)
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    async def archive_trainer_exercise(self, *, authorization: str | None, trainer_user_id: str, row_id: str) -> None:
        try:
            self._require_self_trainer(authorization, trainer_user_id)
            await self._archive_trainer_and_release_media(trainer_user_id, row_id)
            return
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def restore_trainer_exercise(self, *, authorization: str | None, trainer_user_id: str, row_id: str) -> None:
        try:
            self._require_self_trainer(authorization, trainer_user_id)
            with self._runtime.plan_service_scope() as plan_service:
                plan_service.restore_trainer_exercise(
                    self._request_factory.to_restore_trainer_exercise_command(trainer_user_id, row_id)
                )
                return
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    async def upload_trainer_exercise_video(
        self,
        *,
        authorization: str | None,
        trainer_user_id: str,
        row_id: str,
        filename: str,
        data: bytes,
    ) -> ExerciseVideoUploadResponse:
        try:
            self._require_trainer_owner(authorization, trainer_user_id)
            with self._runtime.plan_service_scope() as plan_service:
                plan_service.get_trainer_exercise(trainer_user_id, row_id)
            storage = self._require_storage()
            object_key = await storage.upload_video(
                owner_id=trainer_user_id,
                row_id=row_id,
                filename=filename,
                data=data,
            )
            try:
                with self._runtime.plan_service_scope() as plan_service:
                    _, previous = plan_service.set_trainer_exercise_video_url(trainer_user_id, row_id, object_key)
            except Exception:
                await self._delete_uploaded_object(storage, object_key)
                raise
            await self._release_replaced_media(storage, previous=previous, new_key=object_key, owner_id=trainer_user_id)
            return ExerciseVideoUploadResponse(
                trainer_user_id=trainer_user_id,
                row_id=row_id,
                video_url=self._signed_media_url(object_key),
            )
        except MediaValidationError as exc:
            self._error_translator.raise_http_error(ValidationError(str(exc)))
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    async def delete_trainer_exercise_video(
        self,
        *,
        authorization: str | None,
        trainer_user_id: str,
        row_id: str,
    ) -> None:
        try:
            self._require_trainer_owner(authorization, trainer_user_id)
            storage = self._runtime.video_storage
            with self._runtime.plan_service_scope() as plan_service:
                _, previous = plan_service.clear_trainer_exercise_video_url(trainer_user_id, row_id)
            await self._release_replaced_media(storage, previous=previous, new_key=None, owner_id=trainer_user_id)
            return
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    async def upload_trainer_exercise_photo(
        self,
        *,
        authorization: str | None,
        trainer_user_id: str,
        row_id: str,
        position: str,
        filename: str,
        data: bytes,
    ) -> ExercisePhotoUploadResponse:
        try:
            self._require_trainer_owner(authorization, trainer_user_id)
            photo_position = self._normalize_photo_position(position)
            with self._runtime.plan_service_scope() as plan_service:
                plan_service.get_trainer_exercise(trainer_user_id, row_id)
            storage = self._require_storage()
            validate_photo_bytes(filename, data, max_bytes=self._runtime.settings.s3_max_photo_bytes)
            object_key = await storage.upload_photo(
                owner_id=trainer_user_id,
                row_id=row_id,
                filename=filename,
                data=data,
                position=photo_position,
            )
            try:
                with self._runtime.plan_service_scope() as plan_service:
                    _, previous = plan_service.set_trainer_exercise_photo_url(
                        trainer_user_id,
                        row_id,
                        photo_position,
                        object_key,
                    )
            except Exception:
                await self._delete_uploaded_object(storage, object_key)
                raise
            await self._release_replaced_media(storage, previous=previous, new_key=object_key, owner_id=trainer_user_id)
            return ExercisePhotoUploadResponse(
                trainer_user_id=trainer_user_id,
                row_id=row_id,
                position=photo_position,  # type: ignore[arg-type]
                image_url=self._signed_media_url(object_key),
            )
        except MediaValidationError as exc:
            self._error_translator.raise_http_error(ValidationError(str(exc)))
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    async def delete_trainer_exercise_photo(
        self,
        *,
        authorization: str | None,
        trainer_user_id: str,
        row_id: str,
        position: str,
    ) -> None:
        try:
            self._require_trainer_owner(authorization, trainer_user_id)
            photo_position = self._normalize_photo_position(position)
            storage = self._runtime.video_storage
            with self._runtime.plan_service_scope() as plan_service:
                _, previous = plan_service.clear_trainer_exercise_photo_url(
                    trainer_user_id,
                    row_id,
                    photo_position,
                )
            await self._release_replaced_media(storage, previous=previous, new_key=None, owner_id=trainer_user_id)
            return
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    async def get_media(
        self,
        object_key: str,
        *,
        expires: str | None,
        signature: str | None,
        if_none_match: str | None = None,
    ) -> Response:
        normalized = normalize_stored_media(object_key) or ""
        if not self._is_allowed_media_key(normalized):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="media key is not allowed")
        try:
            expires_at = self._signer().verify(normalized, expires, signature)
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        storage = self._runtime.video_storage
        if storage is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="s3 media storage is not configured",
            )
        try:
            opened = await self._open_stored_media(storage, normalized)
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        headers = self._media_response_headers(opened, expires_at=expires_at)
        if etag_matches(if_none_match, opened.etag):
            opened.close()
            return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)
        return StreamingResponse(opened.iterator, media_type=opened.content_type, headers=headers)

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
                    items=[self._trainer_exercise_response(item) for item in items],
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
                    items=[self._platform_exercise_response(item) for item in items],
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
                return self._platform_exercise_response(item)
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
                return self._platform_exercise_response(item)
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
                return self._platform_exercise_response(item)
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    async def admin_archive_platform_exercise(self, *, authorization: str | None, row_id: str) -> None:
        try:
            self._require_platform_admin(authorization)
            with self._runtime.plan_service_scope() as plan_service:
                keys = plan_service.archive_platform_exercise(
                    self._request_factory.to_archive_platform_exercise_command(row_id)
                )
            await self._release_media_keys(keys, owner_id=PLATFORM_MEDIA_OWNER)
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
            with self._runtime.plan_service_scope() as plan_service:
                plan_service.get_platform_exercise(row_id)
            storage = self._require_storage()
            object_key = await storage.upload_video(owner_id=PLATFORM_MEDIA_OWNER, row_id=row_id, filename=filename, data=data)
            try:
                with self._runtime.plan_service_scope() as plan_service:
                    _, previous = plan_service.set_platform_exercise_video_url(row_id, object_key)
            except Exception:
                await self._delete_uploaded_object(storage, object_key)
                raise
            await self._release_replaced_media(
                storage,
                previous=previous,
                new_key=object_key,
                owner_id=PLATFORM_MEDIA_OWNER,
            )
            return PlatformExerciseVideoUploadResponse(row_id=row_id, video_url=self._signed_media_url(object_key))
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
                _, previous = plan_service.clear_platform_exercise_video_url(row_id)
            await self._release_replaced_media(storage, previous=previous, new_key=None, owner_id=PLATFORM_MEDIA_OWNER)
            return
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    async def admin_upload_platform_exercise_photo(
        self,
        *,
        authorization: str | None,
        row_id: str,
        position: str,
        filename: str,
        data: bytes,
    ) -> PlatformExercisePhotoUploadResponse:
        try:
            self._require_platform_admin(authorization)
            photo_position = self._normalize_photo_position(position)
            with self._runtime.plan_service_scope() as plan_service:
                plan_service.get_platform_exercise(row_id)
            storage = self._require_storage()
            validate_photo_bytes(filename, data, max_bytes=self._runtime.settings.s3_max_photo_bytes)
            object_key = await storage.upload_photo(
                owner_id=PLATFORM_MEDIA_OWNER,
                row_id=row_id,
                filename=filename,
                data=data,
                position=photo_position,
            )
            try:
                with self._runtime.plan_service_scope() as plan_service:
                    _, previous = plan_service.set_platform_exercise_photo_url(row_id, photo_position, object_key)
            except Exception:
                await self._delete_uploaded_object(storage, object_key)
                raise
            await self._release_replaced_media(
                storage,
                previous=previous,
                new_key=object_key,
                owner_id=PLATFORM_MEDIA_OWNER,
            )
            return PlatformExercisePhotoUploadResponse(
                row_id=row_id,
                position=photo_position,  # type: ignore[arg-type]
                image_url=self._signed_media_url(object_key),
            )
        except MediaValidationError as exc:
            self._error_translator.raise_http_error(ValidationError(str(exc)))
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    async def admin_delete_platform_exercise_photo(
        self,
        *,
        authorization: str | None,
        row_id: str,
        position: str,
    ) -> None:
        try:
            self._require_platform_admin(authorization)
            photo_position = self._normalize_photo_position(position)
            storage = self._runtime.video_storage
            with self._runtime.plan_service_scope() as plan_service:
                _, previous = plan_service.clear_platform_exercise_photo_url(row_id, photo_position)
            await self._release_replaced_media(storage, previous=previous, new_key=None, owner_id=PLATFORM_MEDIA_OWNER)
            return
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    async def admin_archive_exercise(self, *, authorization: str | None, trainer_user_id: str, row_id: str) -> None:
        try:
            self._require_platform_admin(authorization)
            await self._archive_trainer_and_release_media(trainer_user_id, row_id)
            return
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def admin_restore_exercise(self, *, authorization: str | None, trainer_user_id: str, row_id: str) -> None:
        try:
            self._require_platform_admin(authorization)
            with self._runtime.plan_service_scope() as plan_service:
                plan_service.restore_trainer_exercise(
                    self._request_factory.to_restore_trainer_exercise_command(trainer_user_id, row_id)
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

    def get_trainer_generation_policy(
        self,
        *,
        authorization: str | None,
        trainer_user_id: str,
    ) -> GenerationPolicyResponse:
        try:
            self._require_self_trainer(authorization, trainer_user_id)
            with self._runtime.plan_service_scope() as plan_service:
                config = plan_service.get_trainer_generation_policy(trainer_user_id)
                return self._response_factory.from_generation_policy(config)
        except PlanError as exc:
            self._error_translator.raise_http_error(exc)
        raise AssertionError("unreachable")

    def upsert_trainer_generation_policy(
        self,
        *,
        authorization: str | None,
        trainer_user_id: str,
        payload: UpsertGenerationPolicyRequest,
    ) -> GenerationPolicyResponse:
        try:
            self._require_self_trainer(authorization, trainer_user_id)
            config = GenerationPolicyConfig.from_dict(payload.model_dump())
            with self._runtime.plan_service_scope() as plan_service:
                saved = plan_service.upsert_trainer_generation_policy(trainer_user_id, config)
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

    def _require_self_trainer(self, authorization: str | None, trainer_user_id: str) -> AuthUser:
        user = self._require_current_user(authorization)
        if user.user_id != trainer_user_id:
            raise ForbiddenError("not allowed to access another trainer's resources")
        return user

    def _require_trainer_owner(self, authorization: str | None, trainer_user_id: str) -> AuthUser:
        # Загрузка медиа: совпадение id и роль тренера. Чужое упражнение отсекается выборкой по паре.
        user = self._require_self_trainer(authorization, trainer_user_id)
        if user.role != "trainer":
            raise ForbiddenError("trainer role required")
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
    def _normalize_photo_position(position: str) -> str:
        normalized = position.strip().lower()
        if normalized not in {"start", "end"}:
            raise ValidationError("invalid photo position (allowed: start, end)")
        return normalized

    def max_photo_bytes(self) -> int:
        return self._runtime.settings.s3_max_photo_bytes

    def max_video_bytes(self) -> int:
        return self._runtime.settings.s3_max_video_bytes

    def _media_prefixes(self) -> tuple[str, str]:
        storage = self._runtime.video_storage
        photos_prefix = getattr(storage, "photos_prefix", None) if storage is not None else None
        videos_prefix = getattr(storage, "videos_prefix", None) if storage is not None else None
        if photos_prefix and videos_prefix:
            return photos_prefix, videos_prefix
        settings = self._runtime.settings
        return settings.s3_photos_prefix, settings.s3_videos_prefix

    def _signer(self) -> MediaUrlSigner:
        photos_prefix, videos_prefix = self._media_prefixes()
        settings = self._runtime.settings
        return MediaUrlSigner(
            settings.media_url_signing_secret,
            settings.media_url_ttl_seconds,
            photos_prefix=photos_prefix,
            videos_prefix=videos_prefix,
        )

    def _signed_media_url(self, object_key: str) -> str:
        signed = self._signer().sign(object_key)
        if signed is None:
            raise IntegrationError("media url signing is not configured")
        return signed

    def _trainer_exercise_response(self, item: TrainerExercise) -> TrainerExerciseResponse:
        response = TrainerExerciseResponse.model_validate(item, from_attributes=True)
        return response.model_copy(
            update={
                "video_url": self._signer().sign(item.video_url),
                "start_image_url": self._signer().sign(item.start_image_url),
                "end_image_url": self._signer().sign(item.end_image_url),
            }
        )

    def _platform_exercise_response(self, item: PlatformExercise) -> PlatformExerciseResponse:
        response = self._response_factory.from_domain_platform_exercise(item)
        return response.model_copy(
            update={
                "video_url": self._signer().sign(item.video_url),
                "start_image_url": self._signer().sign(item.start_image_url),
                "end_image_url": self._signer().sign(item.end_image_url),
            }
        )

    def _require_storage(self):
        storage = self._runtime.video_storage
        if storage is None:
            raise IntegrationError("s3 media storage is not configured")
        return storage

    def _is_allowed_media_key(self, object_key: str) -> bool:
        photos_prefix, videos_prefix = self._media_prefixes()
        return is_safe_object_key(object_key) and is_internal_media_key(
            object_key,
            photos_prefix=photos_prefix,
            videos_prefix=videos_prefix,
        )

    async def _archive_trainer_and_release_media(self, trainer_user_id: str, row_id: str) -> None:
        with self._runtime.plan_service_scope() as plan_service:
            keys = plan_service.archive_trainer_exercise(
                self._request_factory.to_archive_trainer_exercise_command(trainer_user_id, row_id)
            )
        await self._release_media_keys(keys, owner_id=trainer_user_id)

    async def _release_media_keys(self, keys: list[str], *, owner_id: str) -> None:
        storage = self._runtime.video_storage
        for key in keys:
            await self._release_replaced_media(storage, previous=key, new_key=None, owner_id=owner_id)

    async def _release_replaced_media(self, storage, *, previous: str | None, new_key: str | None, owner_id: str) -> None:
        previous_key = normalize_stored_media(previous)
        current_key = normalize_stored_media(new_key)
        if not previous_key or previous_key == current_key:
            return
        await self._release_owned_media(storage, previous_key, owner_id)

    async def _release_owned_media(self, storage, object_key: str, owner_id: str) -> None:
        # Чужой префикс и всё ещё используемый ключ не удаляем: клоны держат стабильный объект.
        photos_prefix, videos_prefix = self._media_prefixes()
        if not media_key_owned_by(object_key, owner_id, photos_prefix=photos_prefix, videos_prefix=videos_prefix):
            logger.warning("refusing to delete media outside owner prefix owner=%s key=%s", owner_id, object_key)
            return
        with self._runtime.plan_service_scope() as plan_service:
            if plan_service.media_key_reference_count(object_key) > 0:
                logger.info("keeping media object still referenced by another exercise key=%s", object_key)
                return
        if storage is None:
            logger.warning("media storage is not configured; skipped delete key=%s", object_key)
            return
        try:
            await storage.delete_media(object_key)
        except Exception:
            logger.exception("failed to delete media object key=%s", object_key)

    async def _delete_uploaded_object(self, storage, object_key: str) -> None:
        try:
            await storage.delete_media(object_key)
        except Exception:
            logger.exception("failed to delete uploaded media after database error key=%s", object_key)

    async def _open_stored_media(self, storage, object_key: str) -> OpenedMedia:
        opener = getattr(storage, "open_media", None)
        if callable(opener):
            return await opener(object_key)
        data, content_type = await storage.download_media(object_key)
        digest = hashlib.sha256(data).hexdigest()
        return OpenedMedia(
            content_type=content_type,
            etag=f'"{digest}"',
            content_length=len(data),
            iterator=iter([data]),
        )

    def _media_response_headers(self, opened: OpenedMedia, *, expires_at: int) -> dict[str, str]:
        remaining = max(0, expires_at - int(time.time()))
        headers = {
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": f"private, max-age={remaining}",
        }
        if opened.etag:
            headers["ETag"] = opened.etag
        if opened.content_length is not None:
            headers["Content-Length"] = str(opened.content_length)
        return headers
