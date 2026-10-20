from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import datetime, timezone

import httpx
from sqlalchemy import text

from application.config import Settings
from application.db import DatabaseManager
from application.gateways import AuthGateway, ProfileGateway, TenantGateway
from application.generation import build_default_generation_orchestrator
from application.media_storage import S3MediaStorage
from application.notifications.config import NotificationConfig
from application.notifications.dispatcher import NotificationDispatcher
from application.notifications.scheduler import start_notification_scheduler
from application.notifications.telegram import TelegramSender
from application.use_cases import PlanService

logger = logging.getLogger(__name__)


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
            service_token=settings.internal_service_token,
        )
        self._tenant_gateway = TenantGateway(
            http_client=self._http_client,
            tenant_service_url=settings.tenant_service_url,
        )
        self._telegram_client = httpx.Client(timeout=10.0)
        self._telegram_sender = TelegramSender(
            self._telegram_client,
            settings.telegram_bot_token,
            settings.telegram_api_base,
        )
        self._scheduler = None
        self._video_storage = self._build_video_storage(settings)

    @property
    def auth_gateway(self) -> AuthGateway:
        return self._auth_gateway

    @property
    def tenant_gateway(self) -> TenantGateway:
        return self._tenant_gateway

    @property
    def settings(self) -> Settings:
        return self._settings

    @property
    def video_storage(self) -> S3MediaStorage | None:
        return self._video_storage

    @contextmanager
    def plan_service_scope(self):
        session = self._db_manager.create_session()
        try:
            yield PlanService(
                session=session,
                generation_orchestrator=build_default_generation_orchestrator(
                    session,
                    media_storage=self._video_storage,
                ),
                profile_gateway=self._profile_gateway,
                require_profile_completion=self._settings.require_profile_completion,
                media_storage=self._video_storage,
                plan_notice_debounce_seconds=self._settings.notifications_plan_debounce_seconds,
            )
        finally:
            session.close()

    @contextmanager
    def notification_session(self):
        session = self._db_manager.create_session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def start_scheduler(self, *, force: bool = False) -> None:
        if self._scheduler is not None:
            return
        if not force and not self._settings.notifications_scheduler_enabled:
            return
        self._scheduler = start_notification_scheduler(
            self.dispatch_notifications,
            self._settings.notifications_poll_seconds,
        )

    def dispatch_notifications(self, now: datetime | None = None) -> None:
        moment = now if now is not None else datetime.now(timezone.utc).replace(tzinfo=None)
        session = self._db_manager.create_session()
        try:
            NotificationDispatcher(
                session,
                config=NotificationConfig.from_settings(self._settings),
                sender=self._telegram_sender,
                login_lookup=self._auth_gateway.get_logins,
            ).run(moment)
        except Exception:
            session.rollback()
            logger.exception("workout notification dispatch failed")
        finally:
            session.close()

    def check_ready(self) -> bool:
        with self._db_manager.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True

    def shutdown(self) -> None:
        if self._scheduler is not None:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
        self._telegram_client.close()
        self._http_client.close()
        self._db_manager.dispose()

    @staticmethod
    def _build_video_storage(settings: Settings) -> S3MediaStorage | None:
        if not settings.s3_media_enabled:
            return None
        if not settings.s3_endpoint or not settings.s3_access_key or not settings.s3_secret_key:
            return None
        # Клиент MinIO не ходит в бакет при старте: бакет и политика photos/* + videos/* задаёт инфраструктура.
        return S3MediaStorage(
            endpoint=settings.s3_endpoint,
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
            bucket=settings.s3_bucket,
            secure=settings.s3_secure,
            videos_prefix=settings.s3_videos_prefix,
            photos_prefix=settings.s3_photos_prefix,
            max_video_size_bytes=settings.s3_max_video_bytes,
            max_photo_size_bytes=settings.s3_max_photo_bytes,
        )
