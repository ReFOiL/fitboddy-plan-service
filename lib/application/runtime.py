from __future__ import annotations

from contextlib import contextmanager

import httpx
from sqlalchemy import text

from application.config import Settings
from application.db import DatabaseManager
from application.gateways import AuthGateway, ProfileGateway
from application.generation import build_default_generation_orchestrator
from application.media_storage import S3MediaStorage
from application.use_cases import PlanService


class PlanApplicationRuntime:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._db_manager = DatabaseManager(settings.database_url)
        self._http_client = httpx.Client(timeout=settings.http_timeout_seconds)
        self._auth_gateway = AuthGateway(
            http_client=self._http_client,
            auth_service_url=settings.auth_service_url,
        )
        self._profile_gateway = ProfileGateway(
            http_client=self._http_client,
            profile_service_url=settings.profile_service_url,
        )
        self._video_storage = self._build_video_storage(settings)

    @property
    def auth_gateway(self) -> AuthGateway:
        return self._auth_gateway

    @property
    def video_storage(self) -> S3MediaStorage | None:
        return self._video_storage

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

    @staticmethod
    def _build_video_storage(settings: Settings) -> S3MediaStorage | None:
        if not settings.s3_media_enabled:
            return None
        if not settings.s3_endpoint or not settings.s3_access_key or not settings.s3_secret_key:
            return None
        return S3MediaStorage(
            endpoint=settings.s3_endpoint,
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
            bucket=settings.s3_bucket,
            secure=settings.s3_secure,
            videos_prefix=settings.s3_videos_prefix,
        )
