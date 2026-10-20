import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(default="sqlite+pysqlite:///./plan_service.db", alias="DATABASE_URL")
    alembic_ini_path: str = Field(default="alembic.ini", alias="ALEMBIC_INI_PATH")
    profile_service_url: str = Field(default="http://profile-service", alias="PROFILE_SERVICE_URL")
    tenant_service_url: str = Field(default="http://tenant-service:8000", alias="TENANT_SERVICE_URL")
    auth_service_url: str = Field(default="http://auth-service:8000", alias="AUTH_SERVICE_URL")
    require_profile_completion: bool = Field(default=True, alias="REQUIRE_PROFILE_COMPLETION")
    http_timeout_seconds: float = Field(default=5.0, alias="HTTP_TIMEOUT_SECONDS")
    internal_service_token: str = Field(default="", alias="INTERNAL_SERVICE_TOKEN")
    s3_media_enabled: bool = Field(default=False, alias="S3_MEDIA_ENABLED")
    s3_endpoint: str = Field(default="", alias="S3_ENDPOINT")
    s3_access_key: str = Field(default="", alias="S3_ACCESS_KEY")
    s3_secret_key: str = Field(default="", alias="S3_SECRET_KEY")
    s3_bucket: str = Field(default="fitboddy-media", alias="S3_BUCKET")
    s3_secure: bool = Field(default=False, alias="S3_SECURE")
    s3_videos_prefix: str = Field(default="videos/", alias="S3_VIDEOS_PREFIX")
    s3_photos_prefix: str = Field(default="photos/", alias="S3_PHOTOS_PREFIX")
    s3_max_video_bytes: int = Field(default=200 * 1024 * 1024, alias="S3_MAX_VIDEO_BYTES")
    s3_max_photo_bytes: int = Field(default=15 * 1024 * 1024, alias="S3_MAX_PHOTO_BYTES")
    # HMAC для подписанных URL. Пустой секрет запрещает отдачу. Инфра задаёт MEDIA_URL_TTL_SECONDS (пример: 300).
    media_url_signing_secret: str = Field(default="", alias="MEDIA_URL_SIGNING_SECRET")
    media_url_ttl_seconds: int = Field(default=300, alias="MEDIA_URL_TTL_SECONDS")
    # Планировщик в процессе API. Для отдельного воркера оставьте false и поднимите worker.
    notifications_scheduler_enabled: bool = Field(default=False, alias="NOTIFICATIONS_SCHEDULER_ENABLED")
    notifications_poll_seconds: int = Field(default=60, ge=10, le=3600, alias="NOTIFICATIONS_POLL_SECONDS")
    notifications_default_timezone: str = Field(default="Asia/Vladivostok", alias="NOTIFICATIONS_DEFAULT_TIMEZONE")
    notifications_morning_reminder: str = Field(default="09:00", alias="NOTIFICATIONS_MORNING_REMINDER")
    notifications_reminder_lead_minutes: int = Field(
        default=120,
        ge=1,
        le=720,
        alias="NOTIFICATIONS_REMINDER_LEAD_MINUTES",
    )
    notifications_plan_debounce_seconds: int = Field(
        default=900,
        ge=0,
        le=86400,
        alias="NOTIFICATIONS_PLAN_DEBOUNCE_SECONDS",
    )
    notifications_plan_notice_ttl_seconds: int = Field(
        default=7 * 24 * 3600,
        ge=60,
        alias="NOTIFICATIONS_PLAN_NOTICE_TTL_SECONDS",
    )
    notifications_missed_lookback_days: int = Field(default=2, ge=1, le=14, alias="NOTIFICATIONS_MISSED_LOOKBACK_DAYS")
    notifications_link_code_ttl_seconds: int = Field(
        default=900,
        ge=60,
        le=86400,
        alias="NOTIFICATIONS_LINK_CODE_TTL_SECONDS",
    )
    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_api_base: str = Field(default="https://api.telegram.org", alias="TELEGRAM_API_BASE")

    @field_validator("notifications_default_timezone")
    @classmethod
    def _known_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("NOTIFICATIONS_DEFAULT_TIMEZONE is not a known IANA timezone") from exc
        return value

    @field_validator("notifications_morning_reminder")
    @classmethod
    def _morning_clock(cls, value: str) -> str:
        if _HHMM.fullmatch(value) is None:
            raise ValueError("NOTIFICATIONS_MORNING_REMINDER must be HH:MM")
        return value
