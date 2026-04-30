from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(default="sqlite+pysqlite:///./plan_service.db", alias="DATABASE_URL")
    alembic_ini_path: str = Field(default="alembic.ini", alias="ALEMBIC_INI_PATH")
    profile_service_url: str = Field(default="http://profile-service", alias="PROFILE_SERVICE_URL")
    require_profile_completion: bool = Field(default=True, alias="REQUIRE_PROFILE_COMPLETION")
    http_timeout_seconds: float = Field(default=5.0, alias="HTTP_TIMEOUT_SECONDS")
