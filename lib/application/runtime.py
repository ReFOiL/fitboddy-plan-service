from __future__ import annotations

from contextlib import contextmanager

import httpx
from sqlalchemy import text

from application.config import Settings
from application.db import DatabaseManager
from application.gateways import ProfileGateway
from application.generation import build_default_generation_orchestrator
from application.use_cases import PlanService


class PlanApplicationRuntime:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._db_manager = DatabaseManager(settings.database_url)
        self._http_client = httpx.Client(timeout=settings.http_timeout_seconds)
        self._profile_gateway = ProfileGateway(
            http_client=self._http_client,
            profile_service_url=settings.profile_service_url,
        )

    @contextmanager
    def plan_service_scope(self):
        session = self._db_manager.create_session()
        try:
            yield PlanService(
                session=session,
                generation_orchestrator=build_default_generation_orchestrator(session),
                profile_gateway=self._profile_gateway,
                require_profile_completion=self._settings.require_profile_completion,
            )
        finally:
            session.close()

    def check_ready(self) -> bool:
        with self._db_manager.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True

    def shutdown(self) -> None:
        self._http_client.close()
        self._db_manager.dispose()
