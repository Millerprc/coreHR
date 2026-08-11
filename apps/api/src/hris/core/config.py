from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "coreHR API"
    app_env: str = "development"
    api_prefix: str = "/api/v1"
    database_url: str = (
        "postgresql+psycopg://corehr:corehr_dev@127.0.0.1:54329/corehr"
    )
    redis_url: str = "redis://127.0.0.1:63800/0"
    business_timezone: str = "Asia/Shanghai"
    personnel_encryption_keys: dict[str, str] = Field(
        default_factory=dict,
        validation_alias="COREHR_PERSONNEL_ENCRYPTION_KEYS",
    )
    personnel_active_key_version: str | None = Field(
        default=None,
        validation_alias="COREHR_PERSONNEL_ACTIVE_KEY_VERSION",
    )
    personnel_search_key: str | None = Field(
        default=None,
        validation_alias="COREHR_PERSONNEL_SEARCH_KEY",
    )
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://127.0.0.1:5173", "http://localhost:5173"]
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
