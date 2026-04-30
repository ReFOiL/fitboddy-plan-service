from fastapi import APIRouter, Request

from presentation.http.schemas import HealthResponse


class SystemRoutes:
    def __init__(self) -> None:
        self.router = APIRouter(tags=["system"])
        self.router.add_api_route("/health", self.health, methods=["GET"], response_model=HealthResponse)
        self.router.add_api_route("/ready", self.ready, methods=["GET"], response_model=HealthResponse)

    @staticmethod
    def health(request: Request) -> HealthResponse:
        return HealthResponse(**request.app.state.plan_handler.health())

    @staticmethod
    def ready(request: Request) -> HealthResponse:
        return HealthResponse(**request.app.state.plan_handler.ready())
