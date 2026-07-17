from fastapi import APIRouter, Header, Query, Request, Response, status

from presentation.http.schemas import (
    AdminExerciseListResponse,
    ClientExerciseLoadResponse,
    TrainingPlanResponse,
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
