from contextlib import asynccontextmanager

from fastapi import FastAPI

from application.config import Settings
from application.runtime import PlanApplicationRuntime
from presentation.http.error_translator import ErrorTranslator
from presentation.http.handlers.plan_handler import PlanHttpHandler
from presentation.http.request_factory import PlanRequestFactory
from presentation.http.response_factory import PlanResponseFactory
from presentation.http.routes.admin_routes import AdminRoutes
from presentation.http.routes.plan_routes import PlanRoutes
from presentation.http.routes.system_routes import SystemRoutes


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    runtime = PlanApplicationRuntime(settings=settings)
    app.state.plan_handler = PlanHttpHandler(
        runtime=runtime,
        request_factory=PlanRequestFactory(),
        response_factory=PlanResponseFactory(),
        error_translator=ErrorTranslator(),
    )
    try:
        yield
    finally:
        runtime.shutdown()


app = FastAPI(title="plan-service", version="0.1.0", lifespan=lifespan)
app.include_router(SystemRoutes().router)
app.include_router(PlanRoutes().router)
app.include_router(AdminRoutes().router)
