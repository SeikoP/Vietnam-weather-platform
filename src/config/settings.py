from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_env: str = Field(default="local", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    database_url: str = Field(alias="DATABASE_URL")
    database_pool_size: int = Field(default=5, alias="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(default=10, alias="DATABASE_MAX_OVERFLOW")

    open_meteo_archive_url: str = Field(
        default="https://archive-api.open-meteo.com/v1/archive",
        alias="OPEN_METEO_ARCHIVE_URL",
    )
    open_meteo_forecast_url: str = Field(
        default="https://api.open-meteo.com/v1/forecast",
        alias="OPEN_METEO_FORECAST_URL",
    )
    open_meteo_timeout_seconds: int = Field(default=30, alias="OPEN_METEO_TIMEOUT_SECONDS")
    open_meteo_max_retries: int = Field(default=3, alias="OPEN_METEO_MAX_RETRIES")

    discord_notifications_enabled: bool = Field(
        default=False,
        alias="DISCORD_NOTIFICATIONS_ENABLED",
    )
    discord_webhook_url: str | None = Field(default=None, alias="DISCORD_WEBHOOK_URL")

    @field_validator("discord_webhook_url", mode="before")
    @classmethod
    def empty_str_to_none(cls, value: object) -> object:
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    @model_validator(mode="after")
    def require_discord_webhook_when_enabled(self) -> "Settings":
        if self.discord_notifications_enabled and not self.discord_webhook_url:
            raise ValueError(
                "DISCORD_WEBHOOK_URL is required when Discord notifications are enabled"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
