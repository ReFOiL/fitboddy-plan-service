from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(default="sqlite+pysqlite:///./plan_service.db", alias="DATABASE_URL")
    alembic_ini_path: str = Field(default="alembic.ini", alias="ALEMBIC_INI_PATH")
    profile_service_url: str = Field(default="http://profile-service", alias="PROFILE_SERVICE_URL")
    auth_service_url: str = Field(default="http://auth-service:8000", alias="AUTH_SERVICE_URL")
    require_profile_completion: bool = Field(default=True, alias="REQUIRE_PROFILE_COMPLETION")
    http_timeout_seconds: float = Field(default=5.0, alias="HTTP_TIMEOUT_SECONDS")
    s3_media_enabled: bool = Field(default=False, alias="S3_MEDIA_ENABLED")
    s3_endpoint: str = Field(default="", alias="S3_ENDPOINT")
    s3_access_key: str = Field(default="", alias="S3_ACCESS_KEY")
    s3_secret_key: str = Field(default="", alias="S3_SECRET_KEY")
    s3_bucket: str = Field(default="fitboddy-media", alias="S3_BUCKET")
    s3_secure: bool = Field(default=False, alias="S3_SECURE")
    s3_videos_prefix: str = Field(default="videos/", alias="S3_VIDEOS_PREFIX")
