from fastapi import APIRouter, File, Query, Request, Response, UploadFile, status

from presentation.http.schemas import (
    ExerciseVideoUploadResponse,
    GeneratePlanRequest,
    PlanDayResponse,
    TrainerExerciseResponse,
    TrainingPlanResponse,
    UpsertTrainerExerciseRequest,
)


class PlanRoutes:
    def __init__(self) -> None:
        self.router = APIRouter(prefix="/api/v1", tags=["plans"])
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
            "/plans/{plan_id}/days/{day_index}",
            self.get_plan_day,
            methods=["GET"],
            response_model=PlanDayResponse,
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
            "/trainers/media/{object_key:path}",
            self.get_media,
            methods=["GET"],
        )

    @staticmethod
    def generate_plan(request: Request, payload: GeneratePlanRequest) -> TrainingPlanResponse:
        return request.app.state.plan_handler.generate_plan(payload)

    @staticmethod
    def get_active_plan(request: Request, user_id: str) -> TrainingPlanResponse:
        return request.app.state.plan_handler.get_active_plan(user_id)

    @staticmethod
    def get_plan_day(request: Request, plan_id: str, day_index: int) -> PlanDayResponse:
        return request.app.state.plan_handler.get_plan_day(plan_id, day_index)

    @staticmethod
    def list_trainer_exercises(
        request: Request,
        trainer_user_id: str,
        include_archived: bool = Query(default=False),
    ) -> list[TrainerExerciseResponse]:
        return request.app.state.plan_handler.list_trainer_exercises(trainer_user_id, include_archived)

    @staticmethod
    def add_trainer_exercise(
        request: Request,
        trainer_user_id: str,
        payload: UpsertTrainerExerciseRequest,
    ) -> TrainerExerciseResponse:
        return request.app.state.plan_handler.add_trainer_exercise(trainer_user_id, payload)

    @staticmethod
    def get_trainer_exercise(request: Request, trainer_user_id: str, row_id: str) -> TrainerExerciseResponse:
        return request.app.state.plan_handler.get_trainer_exercise(trainer_user_id, row_id)

    @staticmethod
    def update_trainer_exercise(
        request: Request,
        trainer_user_id: str,
        row_id: str,
        payload: UpsertTrainerExerciseRequest,
    ) -> TrainerExerciseResponse:
        return request.app.state.plan_handler.update_trainer_exercise(trainer_user_id, row_id, payload)

    @staticmethod
    def archive_trainer_exercise(request: Request, trainer_user_id: str, row_id: str) -> Response:
        request.app.state.plan_handler.archive_trainer_exercise(trainer_user_id, row_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @staticmethod
    async def upload_trainer_exercise_video(
        request: Request,
        trainer_user_id: str,
        row_id: str,
        file: UploadFile = File(...),
    ) -> ExerciseVideoUploadResponse:
        data = await file.read()
        return await request.app.state.plan_handler.upload_trainer_exercise_video(
            trainer_user_id,
            row_id,
            file.filename or "video.mp4",
            data,
        )

    @staticmethod
    async def delete_trainer_exercise_video(request: Request, trainer_user_id: str, row_id: str) -> Response:
        await request.app.state.plan_handler.delete_trainer_exercise_video(trainer_user_id, row_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @staticmethod
    async def get_media(request: Request, object_key: str):
        return await request.app.state.plan_handler.get_media(object_key)
