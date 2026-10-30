from fastapi import APIRouter, Body, File, Header, Query, Request, Response, UploadFile, status

from presentation.http.upload_limits import read_upload_limited

from presentation.http.schemas import (
    AddPlanDayRequest,
    ChangePlanDayWeekdayRequest,
    ChangePlanDayWeekdayResponse,
    ClientExerciseLoadResponse,
    CompletePlanDayRequest,
    CopyPlanDayRequest,
    CopyPlanWeekRequest,
    CreateEmptyPlanRequest,
    UpdatePlanStartRequest,
    ApplyCatalogSyncRequest,
    ApplyCatalogSyncResponse,
    CatalogSyncPreviewResponse,
    ExercisePhotoUploadResponse,
    ExerciseVideoUploadResponse,
    GeneratePlanRequest,
    GenerationPolicyResponse,
    MuscleResponse,
    PlanDayResponse,
    PlanSlotWriteRequest,
    PlatformExerciseResponse,
    ReplacePlanDayRequest,
    ReorderPlanSlotsRequest,
    TodayWorkoutResponse,
    TrainerExerciseResponse,
    TrainingPlanResponse,
    UpdatePlanDayRequest,
    UpdatePlanSlotRequest,
    UpsertClientLoadRequest,
    UpsertGenerationPolicyRequest,
    UpsertTrainerExerciseRequest,
)


class PlanRoutes:
    def __init__(self) -> None:
        self.router = APIRouter(prefix="/api/v1", tags=["plans"])
        self.router.add_api_route(
            "/muscles",
            self.list_muscles,
            methods=["GET"],
            response_model=list[MuscleResponse],
        )
        self.router.add_api_route(
            "/plans/generate",
            self.generate_plan,
            methods=["POST"],
            status_code=status.HTTP_201_CREATED,
            response_model=TrainingPlanResponse,
        )
        self.router.add_api_route(
            "/plans/users/{user_id}/active",
            self.get_active_plan,
            methods=["GET"],
            response_model=TrainingPlanResponse,
        )
        self.router.add_api_route(
            "/plans/clients/{client_user_id}/trainers/{trainer_user_id}/active",
            self.get_trainer_client_plan,
            methods=["GET"],
            response_model=TrainingPlanResponse,
        )
        self.router.add_api_route(
            "/plans/clients/{client_user_id}/trainers/{trainer_user_id}/active",
            self.create_empty_plan,
            methods=["POST"],
            status_code=status.HTTP_201_CREATED,
            response_model=TrainingPlanResponse,
        )
        self.router.add_api_route(
            "/plans/clients/{client_user_id}/trainers/{trainer_user_id}/start",
            self.update_plan_start,
            methods=["PATCH"],
            response_model=TrainingPlanResponse,
        )
        self.router.add_api_route(
            "/plans/clients/{client_user_id}/trainers/{trainer_user_id}/days/{day_index}",
            self.replace_plan_day_slots,
            methods=["PUT"],
            response_model=PlanDayResponse,
        )
        self.router.add_api_route(
            "/plans/clients/{client_user_id}/trainers/{trainer_user_id}/days/{day_index}/exercises",
            self.add_plan_slot,
            methods=["POST"],
            status_code=status.HTTP_201_CREATED,
            response_model=PlanDayResponse,
        )
        self.router.add_api_route(
            "/plans/clients/{client_user_id}/trainers/{trainer_user_id}/days/{day_index}/exercises/order",
            self.reorder_plan_slots,
            methods=["PUT"],
            response_model=PlanDayResponse,
        )
        self.router.add_api_route(
            "/plans/clients/{client_user_id}/trainers/{trainer_user_id}/days/{day_index}/exercises/{line_id}",
            self.update_plan_slot,
            methods=["PATCH"],
            response_model=PlanDayResponse,
        )
        self.router.add_api_route(
            "/plans/clients/{client_user_id}/trainers/{trainer_user_id}/days/{day_index}/exercises/{line_id}",
            self.delete_plan_slot,
            methods=["DELETE"],
            status_code=status.HTTP_204_NO_CONTENT,
            response_class=Response,
        )
        self.router.add_api_route(
            "/plans/clients/{client_user_id}/trainers/{trainer_user_id}/days",
            self.add_plan_day,
            methods=["POST"],
            status_code=status.HTTP_201_CREATED,
            response_model=TrainingPlanResponse,
        )
        self.router.add_api_route(
            "/plans/clients/{client_user_id}/trainers/{trainer_user_id}/days/{day_index}",
            self.remove_plan_day,
            methods=["DELETE"],
            response_model=TrainingPlanResponse,
        )
        self.router.add_api_route(
            "/plans/clients/{client_user_id}/trainers/{trainer_user_id}/days/{day_index}",
            self.update_plan_day,
            methods=["PATCH"],
            response_model=PlanDayResponse,
        )
        self.router.add_api_route(
            "/plans/clients/{client_user_id}/trainers/{trainer_user_id}/days/{day_index}/weekday",
            self.change_plan_day_weekday,
            methods=["POST"],
            response_model=ChangePlanDayWeekdayResponse,
        )
        self.router.add_api_route(
            "/plans/clients/{client_user_id}/trainers/{trainer_user_id}/days/{day_index}/copy",
            self.copy_plan_day,
            methods=["POST"],
            response_model=TrainingPlanResponse,
        )
        self.router.add_api_route(
            "/plans/clients/{client_user_id}/trainers/{trainer_user_id}/weeks/{week}/copy",
            self.copy_plan_week,
            methods=["POST"],
            response_model=TrainingPlanResponse,
        )
        self.router.add_api_route(
            "/plans/me/today",
            self.get_today_workout,
            methods=["GET"],
            response_model=TodayWorkoutResponse,
        )
        self.router.add_api_route(
            "/plans/me/days/{day_index}/complete",
            self.complete_plan_day,
            methods=["POST"],
            response_model=TodayWorkoutResponse,
        )
        self.router.add_api_route(
            "/plans/me/days/{day_index}/exercises/{line_id}/replace",
            self.replace_plan_exercise,
            methods=["POST"],
            response_model=TodayWorkoutResponse,
        )
        self.router.add_api_route(
            "/plans/{plan_id}/days/{day_index}",
            self.get_plan_day,
            methods=["GET"],
            response_model=PlanDayResponse,
        )
        self.router.add_api_route(
            "/trainers/{trainer_user_id}/generation-policy",
            self.get_trainer_generation_policy,
            methods=["GET"],
            response_model=GenerationPolicyResponse,
        )
        self.router.add_api_route(
            "/trainers/{trainer_user_id}/generation-policy",
            self.upsert_trainer_generation_policy,
            methods=["PUT"],
            response_model=GenerationPolicyResponse,
        )
        self.router.add_api_route(
            "/trainers/{trainer_user_id}/exercises",
            self.list_trainer_exercises,
            methods=["GET"],
            response_model=list[TrainerExerciseResponse],
        )
        self.router.add_api_route(
            "/trainers/{trainer_user_id}/exercises",
            self.add_trainer_exercise,
            methods=["POST"],
            status_code=status.HTTP_201_CREATED,
            response_model=TrainerExerciseResponse,
        )
        self.router.add_api_route(
            "/trainers/{trainer_user_id}/exercises/sync-preview",
            self.preview_catalog_sync,
            methods=["GET"],
            response_model=CatalogSyncPreviewResponse,
        )
        self.router.add_api_route(
            "/trainers/{trainer_user_id}/exercises/sync",
            self.apply_catalog_sync,
            methods=["POST"],
            response_model=ApplyCatalogSyncResponse,
        )
        self.router.add_api_route(
            "/trainers/{trainer_user_id}/exercises/{row_id}",
            self.get_trainer_exercise,
            methods=["GET"],
            response_model=TrainerExerciseResponse,
        )
        self.router.add_api_route(
            "/trainers/{trainer_user_id}/exercises/{row_id}",
            self.update_trainer_exercise,
            methods=["PUT"],
            response_model=TrainerExerciseResponse,
        )
        self.router.add_api_route(
            "/trainers/{trainer_user_id}/exercises/{row_id}/archive",
            self.archive_trainer_exercise,
            methods=["POST"],
            status_code=status.HTTP_204_NO_CONTENT,
            response_class=Response,
        )
        self.router.add_api_route(
            "/trainers/{trainer_user_id}/exercises/{row_id}/restore",
            self.restore_trainer_exercise,
            methods=["POST"],
            status_code=status.HTTP_204_NO_CONTENT,
            response_class=Response,
        )
        self.router.add_api_route(
            "/trainers/{trainer_user_id}/exercises/{row_id}/video",
            self.upload_trainer_exercise_video,
            methods=["POST"],
            response_model=ExerciseVideoUploadResponse,
        )
        self.router.add_api_route(
            "/trainers/{trainer_user_id}/exercises/{row_id}/video",
            self.delete_trainer_exercise_video,
            methods=["DELETE"],
            status_code=status.HTTP_204_NO_CONTENT,
            response_class=Response,
        )
        self.router.add_api_route(
            "/trainers/{trainer_user_id}/exercises/{row_id}/photos/{position}",
            self.upload_trainer_exercise_photo,
            methods=["POST"],
            response_model=ExercisePhotoUploadResponse,
        )
        self.router.add_api_route(
            "/trainers/{trainer_user_id}/exercises/{row_id}/photos/{position}",
            self.delete_trainer_exercise_photo,
            methods=["DELETE"],
            status_code=status.HTTP_204_NO_CONTENT,
            response_class=Response,
        )
        self.router.add_api_route(
            "/trainers/media/{object_key:path}",
            self.get_media,
            methods=["GET"],
        )
        self.router.add_api_route(
            "/plans/clients/{client_user_id}/trainers/{trainer_user_id}/loads",
            self.list_client_loads,
            methods=["GET"],
            response_model=list[ClientExerciseLoadResponse],
        )
        self.router.add_api_route(
            "/plans/clients/{client_user_id}/trainers/{trainer_user_id}/loads/{exercise_row_id}",
            self.upsert_client_load,
            methods=["PUT"],
            response_model=ClientExerciseLoadResponse,
        )
        self.router.add_api_route(
            "/plans/clients/{client_user_id}/platform/loads",
            self.list_client_platform_loads,
            methods=["GET"],
            response_model=list[ClientExerciseLoadResponse],
        )
        self.router.add_api_route(
            "/plans/clients/{client_user_id}/platform/loads/{exercise_row_id}",
            self.upsert_client_platform_load,
            methods=["PUT"],
            response_model=ClientExerciseLoadResponse,
        )
        self.router.add_api_route(
            "/platform-exercises",
            self.list_active_platform_exercises,
            methods=["GET"],
            response_model=list[PlatformExerciseResponse],
        )
        self.router.add_api_route(
            "/platform-exercises/{row_id}",
            self.get_active_platform_exercise,
            methods=["GET"],
            response_model=PlatformExerciseResponse,
        )

    @staticmethod
    def list_muscles(request: Request) -> list[MuscleResponse]:
        return request.app.state.plan_handler.list_muscles()

    @staticmethod
    def generate_plan(
        request: Request,
        payload: GeneratePlanRequest,
        authorization: str | None = Header(default=None),
    ) -> TrainingPlanResponse:
        return request.app.state.plan_handler.generate_plan(authorization=authorization, payload=payload)

    @staticmethod
    def get_active_plan(
        request: Request,
        user_id: str,
        authorization: str | None = Header(default=None),
    ) -> TrainingPlanResponse:
        return request.app.state.plan_handler.get_active_plan(authorization=authorization, user_id=user_id)

    @staticmethod
    def get_trainer_client_plan(
        request: Request,
        client_user_id: str,
        trainer_user_id: str,
        authorization: str | None = Header(default=None),
    ) -> TrainingPlanResponse:
        return request.app.state.plan_handler.get_trainer_client_plan(
            authorization=authorization,
            client_user_id=client_user_id,
            trainer_user_id=trainer_user_id,
        )

    @staticmethod
    def create_empty_plan(
        request: Request,
        client_user_id: str,
        trainer_user_id: str,
        payload: CreateEmptyPlanRequest,
        authorization: str | None = Header(default=None),
    ) -> TrainingPlanResponse:
        return request.app.state.plan_handler.create_empty_plan(
            authorization=authorization,
            client_user_id=client_user_id,
            trainer_user_id=trainer_user_id,
            payload=payload,
        )

    @staticmethod
    def update_plan_start(
        request: Request,
        client_user_id: str,
        trainer_user_id: str,
        payload: UpdatePlanStartRequest,
        authorization: str | None = Header(default=None),
    ) -> TrainingPlanResponse:
        return request.app.state.plan_handler.update_plan_start(
            authorization=authorization,
            client_user_id=client_user_id,
            trainer_user_id=trainer_user_id,
            payload=payload,
        )

    @staticmethod
    def replace_plan_day_slots(
        request: Request,
        client_user_id: str,
        trainer_user_id: str,
        day_index: int,
        payload: ReplacePlanDayRequest,
        authorization: str | None = Header(default=None),
    ) -> PlanDayResponse:
        return request.app.state.plan_handler.replace_plan_day_slots(
            authorization=authorization,
            client_user_id=client_user_id,
            trainer_user_id=trainer_user_id,
            day_index=day_index,
            payload=payload,
        )

    @staticmethod
    def add_plan_slot(
        request: Request,
        client_user_id: str,
        trainer_user_id: str,
        day_index: int,
        payload: PlanSlotWriteRequest,
        authorization: str | None = Header(default=None),
    ) -> PlanDayResponse:
        return request.app.state.plan_handler.add_plan_slot(
            authorization=authorization,
            client_user_id=client_user_id,
            trainer_user_id=trainer_user_id,
            day_index=day_index,
            payload=payload,
        )

    @staticmethod
    def reorder_plan_slots(
        request: Request,
        client_user_id: str,
        trainer_user_id: str,
        day_index: int,
        payload: ReorderPlanSlotsRequest,
        authorization: str | None = Header(default=None),
    ) -> PlanDayResponse:
        return request.app.state.plan_handler.reorder_plan_slots(
            authorization=authorization,
            client_user_id=client_user_id,
            trainer_user_id=trainer_user_id,
            day_index=day_index,
            payload=payload,
        )

    @staticmethod
    def update_plan_slot(
        request: Request,
        client_user_id: str,
        trainer_user_id: str,
        day_index: int,
        line_id: str,
        payload: UpdatePlanSlotRequest,
        authorization: str | None = Header(default=None),
    ) -> PlanDayResponse:
        return request.app.state.plan_handler.update_plan_slot(
            authorization=authorization,
            client_user_id=client_user_id,
            trainer_user_id=trainer_user_id,
            day_index=day_index,
            line_id=line_id,
            payload=payload,
        )

    @staticmethod
    def delete_plan_slot(
        request: Request,
        client_user_id: str,
        trainer_user_id: str,
        day_index: int,
        line_id: str,
        authorization: str | None = Header(default=None),
    ) -> Response:
        request.app.state.plan_handler.delete_plan_slot(
            authorization=authorization,
            client_user_id=client_user_id,
            trainer_user_id=trainer_user_id,
            day_index=day_index,
            line_id=line_id,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @staticmethod
    def get_plan_day(
        request: Request,
        plan_id: str,
        day_index: int,
        authorization: str | None = Header(default=None),
    ) -> PlanDayResponse:
        return request.app.state.plan_handler.get_plan_day(
            authorization=authorization,
            plan_id=plan_id,
            day_index=day_index,
        )

    @staticmethod
    def get_today_workout(
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> TodayWorkoutResponse:
        return request.app.state.plan_handler.get_today_workout(authorization=authorization)

    @staticmethod
    def complete_plan_day(
        request: Request,
        day_index: int,
        authorization: str | None = Header(default=None),
        payload: CompletePlanDayRequest | None = Body(default=None),
    ) -> TodayWorkoutResponse:
        return request.app.state.plan_handler.complete_plan_day(
            authorization=authorization,
            day_index=day_index,
            payload=payload,
        )

    @staticmethod
    def add_plan_day(
        request: Request,
        client_user_id: str,
        trainer_user_id: str,
        payload: AddPlanDayRequest,
        authorization: str | None = Header(default=None),
    ) -> TrainingPlanResponse:
        return request.app.state.plan_handler.add_plan_day(
            authorization=authorization,
            client_user_id=client_user_id,
            trainer_user_id=trainer_user_id,
            payload=payload,
        )

    @staticmethod
    def remove_plan_day(
        request: Request,
        client_user_id: str,
        trainer_user_id: str,
        day_index: int,
        authorization: str | None = Header(default=None),
    ) -> TrainingPlanResponse:
        return request.app.state.plan_handler.remove_plan_day(
            authorization=authorization,
            client_user_id=client_user_id,
            trainer_user_id=trainer_user_id,
            day_index=day_index,
        )

    @staticmethod
    def update_plan_day(
        request: Request,
        client_user_id: str,
        trainer_user_id: str,
        day_index: int,
        payload: UpdatePlanDayRequest,
        authorization: str | None = Header(default=None),
    ) -> PlanDayResponse:
        return request.app.state.plan_handler.update_plan_day(
            authorization=authorization,
            client_user_id=client_user_id,
            trainer_user_id=trainer_user_id,
            day_index=day_index,
            payload=payload,
        )

    @staticmethod
    def change_plan_day_weekday(
        request: Request,
        client_user_id: str,
        trainer_user_id: str,
        day_index: int,
        payload: ChangePlanDayWeekdayRequest,
        authorization: str | None = Header(default=None),
    ) -> ChangePlanDayWeekdayResponse:
        return request.app.state.plan_handler.change_plan_day_weekday(
            authorization=authorization,
            client_user_id=client_user_id,
            trainer_user_id=trainer_user_id,
            day_index=day_index,
            payload=payload,
        )

    @staticmethod
    def copy_plan_day(
        request: Request,
        client_user_id: str,
        trainer_user_id: str,
        day_index: int,
        payload: CopyPlanDayRequest,
        authorization: str | None = Header(default=None),
    ) -> TrainingPlanResponse:
        return request.app.state.plan_handler.copy_plan_day(
            authorization=authorization,
            client_user_id=client_user_id,
            trainer_user_id=trainer_user_id,
            day_index=day_index,
            payload=payload,
        )

    @staticmethod
    def copy_plan_week(
        request: Request,
        client_user_id: str,
        trainer_user_id: str,
        week: int,
        payload: CopyPlanWeekRequest,
        authorization: str | None = Header(default=None),
    ) -> TrainingPlanResponse:
        return request.app.state.plan_handler.copy_plan_week(
            authorization=authorization,
            client_user_id=client_user_id,
            trainer_user_id=trainer_user_id,
            week=week,
            payload=payload,
        )

    @staticmethod
    def replace_plan_exercise(
        request: Request,
        day_index: int,
        line_id: str,
        authorization: str | None = Header(default=None),
    ) -> TodayWorkoutResponse:
        return request.app.state.plan_handler.replace_plan_exercise(
            authorization=authorization,
            day_index=day_index,
            line_id=line_id,
        )

    @staticmethod
    def get_trainer_generation_policy(
        request: Request,
        trainer_user_id: str,
        authorization: str | None = Header(default=None),
    ) -> GenerationPolicyResponse:
        return request.app.state.plan_handler.get_trainer_generation_policy(
            authorization=authorization,
            trainer_user_id=trainer_user_id,
        )

    @staticmethod
    def upsert_trainer_generation_policy(
        request: Request,
        trainer_user_id: str,
        payload: UpsertGenerationPolicyRequest,
        authorization: str | None = Header(default=None),
    ) -> GenerationPolicyResponse:
        return request.app.state.plan_handler.upsert_trainer_generation_policy(
            authorization=authorization,
            trainer_user_id=trainer_user_id,
            payload=payload,
        )

    @staticmethod
    def list_trainer_exercises(
        request: Request,
        trainer_user_id: str,
        include_archived: bool = Query(default=False),
        authorization: str | None = Header(default=None),
    ) -> list[TrainerExerciseResponse]:
        return request.app.state.plan_handler.list_trainer_exercises(
            authorization=authorization,
            trainer_user_id=trainer_user_id,
            include_archived=include_archived,
        )

    @staticmethod
    def add_trainer_exercise(
        request: Request,
        trainer_user_id: str,
        payload: UpsertTrainerExerciseRequest,
        authorization: str | None = Header(default=None),
    ) -> TrainerExerciseResponse:
        return request.app.state.plan_handler.add_trainer_exercise(
            authorization=authorization,
            trainer_user_id=trainer_user_id,
            payload=payload,
        )

    @staticmethod
    def preview_catalog_sync(
        request: Request,
        trainer_user_id: str,
        authorization: str | None = Header(default=None),
    ) -> CatalogSyncPreviewResponse:
        return request.app.state.plan_handler.preview_catalog_sync(
            authorization=authorization,
            trainer_user_id=trainer_user_id,
        )

    @staticmethod
    async def apply_catalog_sync(
        request: Request,
        trainer_user_id: str,
        payload: ApplyCatalogSyncRequest,
        authorization: str | None = Header(default=None),
    ) -> ApplyCatalogSyncResponse:
        return await request.app.state.plan_handler.apply_catalog_sync(
            authorization=authorization,
            trainer_user_id=trainer_user_id,
            payload=payload,
        )

    @staticmethod
    def get_trainer_exercise(
        request: Request,
        trainer_user_id: str,
        row_id: str,
        authorization: str | None = Header(default=None),
    ) -> TrainerExerciseResponse:
        return request.app.state.plan_handler.get_trainer_exercise(
            authorization=authorization,
            trainer_user_id=trainer_user_id,
            row_id=row_id,
        )

    @staticmethod
    def update_trainer_exercise(
        request: Request,
        trainer_user_id: str,
        row_id: str,
        payload: UpsertTrainerExerciseRequest,
        authorization: str | None = Header(default=None),
    ) -> TrainerExerciseResponse:
        return request.app.state.plan_handler.update_trainer_exercise(
            authorization=authorization,
            trainer_user_id=trainer_user_id,
            row_id=row_id,
            payload=payload,
        )

    @staticmethod
    async def archive_trainer_exercise(
        request: Request,
        trainer_user_id: str,
        row_id: str,
        authorization: str | None = Header(default=None),
    ) -> Response:
        await request.app.state.plan_handler.archive_trainer_exercise(
            authorization=authorization,
            trainer_user_id=trainer_user_id,
            row_id=row_id,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @staticmethod
    def restore_trainer_exercise(
        request: Request,
        trainer_user_id: str,
        row_id: str,
        authorization: str | None = Header(default=None),
    ) -> Response:
        request.app.state.plan_handler.restore_trainer_exercise(
            authorization=authorization,
            trainer_user_id=trainer_user_id,
            row_id=row_id,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @staticmethod
    async def upload_trainer_exercise_video(
        request: Request,
        trainer_user_id: str,
        row_id: str,
        file: UploadFile = File(...),
        authorization: str | None = Header(default=None),
    ) -> ExerciseVideoUploadResponse:
        data = await read_upload_limited(file, request.app.state.plan_handler.max_video_bytes())
        return await request.app.state.plan_handler.upload_trainer_exercise_video(
            authorization=authorization,
            trainer_user_id=trainer_user_id,
            row_id=row_id,
            filename=file.filename or "video.mp4",
            data=data,
        )

    @staticmethod
    async def delete_trainer_exercise_video(
        request: Request,
        trainer_user_id: str,
        row_id: str,
        authorization: str | None = Header(default=None),
    ) -> Response:
        await request.app.state.plan_handler.delete_trainer_exercise_video(
            authorization=authorization,
            trainer_user_id=trainer_user_id,
            row_id=row_id,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @staticmethod
    async def upload_trainer_exercise_photo(
        request: Request,
        trainer_user_id: str,
        row_id: str,
        position: str,
        file: UploadFile = File(...),
        authorization: str | None = Header(default=None),
    ) -> ExercisePhotoUploadResponse:
        data = await read_upload_limited(file, request.app.state.plan_handler.max_photo_bytes())
        return await request.app.state.plan_handler.upload_trainer_exercise_photo(
            authorization=authorization,
            trainer_user_id=trainer_user_id,
            row_id=row_id,
            position=position,
            filename=file.filename or "photo.jpg",
            data=data,
        )

    @staticmethod
    async def delete_trainer_exercise_photo(
        request: Request,
        trainer_user_id: str,
        row_id: str,
        position: str,
        authorization: str | None = Header(default=None),
    ) -> Response:
        await request.app.state.plan_handler.delete_trainer_exercise_photo(
            authorization=authorization,
            trainer_user_id=trainer_user_id,
            row_id=row_id,
            position=position,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @staticmethod
    async def get_media(
        request: Request,
        object_key: str,
        expires: str | None = Query(default=None),
        signature: str | None = Query(default=None),
        if_none_match: str | None = Header(default=None, alias="If-None-Match"),
    ):
        return await request.app.state.plan_handler.get_media(
            object_key,
            expires=expires,
            signature=signature,
            if_none_match=if_none_match,
        )

    @staticmethod
    def list_client_loads(
        request: Request,
        client_user_id: str,
        trainer_user_id: str,
        authorization: str | None = Header(default=None),
    ) -> list[ClientExerciseLoadResponse]:
        return request.app.state.plan_handler.list_client_loads(
            authorization=authorization,
            client_user_id=client_user_id,
            trainer_user_id=trainer_user_id,
        )

    @staticmethod
    def upsert_client_load(
        request: Request,
        client_user_id: str,
        trainer_user_id: str,
        exercise_row_id: str,
        payload: UpsertClientLoadRequest,
        authorization: str | None = Header(default=None),
    ) -> ClientExerciseLoadResponse:
        return request.app.state.plan_handler.upsert_client_load(
            authorization=authorization,
            client_user_id=client_user_id,
            trainer_user_id=trainer_user_id,
            exercise_row_id=exercise_row_id,
            payload=payload,
        )

    @staticmethod
    def list_client_platform_loads(
        request: Request,
        client_user_id: str,
        authorization: str | None = Header(default=None),
    ) -> list[ClientExerciseLoadResponse]:
        return request.app.state.plan_handler.list_client_platform_loads(
            authorization=authorization,
            client_user_id=client_user_id,
        )

    @staticmethod
    def upsert_client_platform_load(
        request: Request,
        client_user_id: str,
        exercise_row_id: str,
        payload: UpsertClientLoadRequest,
        authorization: str | None = Header(default=None),
    ) -> ClientExerciseLoadResponse:
        return request.app.state.plan_handler.upsert_client_platform_load(
            authorization=authorization,
            client_user_id=client_user_id,
            exercise_row_id=exercise_row_id,
            payload=payload,
        )

    @staticmethod
    def list_active_platform_exercises(request: Request) -> list[PlatformExerciseResponse]:
        return request.app.state.plan_handler.list_active_platform_exercises()

    @staticmethod
    def get_active_platform_exercise(request: Request, row_id: str) -> PlatformExerciseResponse:
        return request.app.state.plan_handler.get_active_platform_exercise(row_id)
