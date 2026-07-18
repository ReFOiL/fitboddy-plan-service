from fastapi import APIRouter, File, Header, Query, Request, Response, UploadFile, status

from presentation.http.schemas import (
    AdminExerciseListResponse,
    AdminPlatformExerciseListResponse,
    ClientExerciseLoadResponse,
    GenerationPolicyResponse,
    PlatformExerciseResponse,
    PlatformExerciseVideoUploadResponse,
    TrainingPlanResponse,
    UpsertGenerationPolicyRequest,
    UpsertPlatformExerciseRequest,
)


class AdminRoutes:
    def __init__(self) -> None:
        self.router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
        self.router.add_api_route(
            "/exercises",
            self.list_exercises,
            methods=["GET"],
            response_model=AdminExerciseListResponse,
        )
        self.router.add_api_route(
            "/exercises/{trainer_user_id}/{row_id}/archive",
            self.archive_exercise,
            methods=["POST"],
            status_code=status.HTTP_204_NO_CONTENT,
        )
        self.router.add_api_route(
            "/platform-exercises",
            self.list_platform_exercises,
            methods=["GET"],
            response_model=AdminPlatformExerciseListResponse,
        )
        self.router.add_api_route(
            "/platform-exercises",
            self.create_platform_exercise,
            methods=["POST"],
            response_model=PlatformExerciseResponse,
            status_code=status.HTTP_201_CREATED,
        )
        self.router.add_api_route(
            "/platform-exercises/{row_id}",
            self.get_platform_exercise,
            methods=["GET"],
            response_model=PlatformExerciseResponse,
        )
        self.router.add_api_route(
            "/platform-exercises/{row_id}",
            self.update_platform_exercise,
            methods=["PUT"],
            response_model=PlatformExerciseResponse,
        )
        self.router.add_api_route(
            "/platform-exercises/{row_id}/archive",
            self.archive_platform_exercise,
            methods=["POST"],
            status_code=status.HTTP_204_NO_CONTENT,
        )
        self.router.add_api_route(
            "/platform-exercises/{row_id}/video",
            self.upload_platform_exercise_video,
            methods=["POST"],
            response_model=PlatformExerciseVideoUploadResponse,
        )
        self.router.add_api_route(
            "/platform-exercises/{row_id}/video",
            self.delete_platform_exercise_video,
            methods=["DELETE"],
            status_code=status.HTTP_204_NO_CONTENT,
        )
        self.router.add_api_route(
            "/plans/users/{user_id}/active",
            self.get_active_plan,
            methods=["GET"],
            response_model=TrainingPlanResponse,
        )
        self.router.add_api_route(
            "/plans/clients/{client_user_id}/trainers/{trainer_user_id}/loads",
            self.list_loads,
            methods=["GET"],
            response_model=list[ClientExerciseLoadResponse],
        )
        self.router.add_api_route(
            "/generation-policy",
            self.get_generation_policy,
            methods=["GET"],
            response_model=GenerationPolicyResponse,
        )
        self.router.add_api_route(
            "/generation-policy",
            self.upsert_generation_policy,
            methods=["PUT"],
            response_model=GenerationPolicyResponse,
        )

    def list_exercises(
        self,
        request: Request,
        authorization: str | None = Header(default=None, alias="Authorization"),
        trainer_user_id: str | None = Query(default=None),
        include_archived: bool = Query(default=True),
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=20, ge=1, le=100),
    ) -> AdminExerciseListResponse:
        return request.app.state.plan_handler.admin_list_exercises(
            authorization=authorization,
            trainer_user_id=trainer_user_id,
            include_archived=include_archived,
            page=page,
            page_size=page_size,
        )

    def archive_exercise(
        self,
        trainer_user_id: str,
        row_id: str,
        request: Request,
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> Response:
        request.app.state.plan_handler.admin_archive_exercise(
            authorization=authorization,
            trainer_user_id=trainer_user_id,
            row_id=row_id,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    def list_platform_exercises(
        self,
        request: Request,
        authorization: str | None = Header(default=None, alias="Authorization"),
        include_archived: bool = Query(default=True),
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=20, ge=1, le=100),
    ) -> AdminPlatformExerciseListResponse:
        return request.app.state.plan_handler.admin_list_platform_exercises(
            authorization=authorization,
            include_archived=include_archived,
            page=page,
            page_size=page_size,
        )

    def create_platform_exercise(
        self,
        payload: UpsertPlatformExerciseRequest,
        request: Request,
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> PlatformExerciseResponse:
        return request.app.state.plan_handler.admin_create_platform_exercise(
            authorization=authorization,
            payload=payload,
        )

    def get_platform_exercise(
        self,
        row_id: str,
        request: Request,
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> PlatformExerciseResponse:
        return request.app.state.plan_handler.admin_get_platform_exercise(
            authorization=authorization,
            row_id=row_id,
        )

    def update_platform_exercise(
        self,
        row_id: str,
        payload: UpsertPlatformExerciseRequest,
        request: Request,
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> PlatformExerciseResponse:
        return request.app.state.plan_handler.admin_update_platform_exercise(
            authorization=authorization,
            row_id=row_id,
            payload=payload,
        )

    def archive_platform_exercise(
        self,
        row_id: str,
        request: Request,
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> Response:
        request.app.state.plan_handler.admin_archive_platform_exercise(
            authorization=authorization,
            row_id=row_id,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    async def upload_platform_exercise_video(
        self,
        row_id: str,
        request: Request,
        authorization: str | None = Header(default=None, alias="Authorization"),
        file: UploadFile = File(...),
    ) -> PlatformExerciseVideoUploadResponse:
        data = await file.read()
        return await request.app.state.plan_handler.admin_upload_platform_exercise_video(
            authorization=authorization,
            row_id=row_id,
            filename=file.filename or "video.mp4",
            data=data,
        )

    async def delete_platform_exercise_video(
        self,
        row_id: str,
        request: Request,
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> Response:
        await request.app.state.plan_handler.admin_delete_platform_exercise_video(
            authorization=authorization,
            row_id=row_id,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    def get_active_plan(
        self,
        user_id: str,
        request: Request,
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> TrainingPlanResponse:
        return request.app.state.plan_handler.admin_get_active_plan(authorization=authorization, user_id=user_id)

    def list_loads(
        self,
        client_user_id: str,
        trainer_user_id: str,
        request: Request,
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> list[ClientExerciseLoadResponse]:
        return request.app.state.plan_handler.admin_list_client_loads(
            authorization=authorization,
            client_user_id=client_user_id,
            trainer_user_id=trainer_user_id,
        )

    def get_generation_policy(
        self,
        request: Request,
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> GenerationPolicyResponse:
        return request.app.state.plan_handler.admin_get_generation_policy(authorization=authorization)

    def upsert_generation_policy(
        self,
        request: Request,
        payload: UpsertGenerationPolicyRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> GenerationPolicyResponse:
        return request.app.state.plan_handler.admin_upsert_generation_policy(
            authorization=authorization,
            payload=payload,
        )
