from functools import lru_cache
import json
from typing import Any

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # The production source of truth must be Neon/PostgreSQL, never Space disk.
    database_url: str = "postgresql+psycopg://web_radar:replace-me@localhost:5432/web_radar"
    app_env: str = "production"
    log_level: str = "INFO"
    scheduler_poll_interval_seconds: float = Field(
        default=10.0,
        validation_alias=AliasChoices(
            "scheduler_poll_interval_seconds",
            "scheduler_interval",
            "poll_interval_seconds",
        ),
    )
    scheduler_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "scheduler_enabled",
            "enable_scheduler",
            "enable_background_scheduler",
        ),
    )


    # Bright Data Scraper Studio Configuration
    bright_data_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("bright_data_api_key", "brightdata_api_key"),
    )
    bright_data_collector_id: str | None = Field(
        default="c_msz0zrtw29tjzhzakl",
        validation_alias=AliasChoices("bright_data_collector_id", "brightdata_collector_id"),
    )
    bright_data_base_url: str = "https://api.brightdata.com"
    bright_data_poll_timeout_seconds: float = 60.0
    bright_data_poll_interval_seconds: float = 2.0

    # Gemini LLM Planner Configuration
    gemini_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "gemini_api_key",
            "google_api_key",
            "gemini_key",
            "gemeni_key",
            "gemeni_api_key",
        ),
    )
    gemini_model_name: str = Field(
        default="gemini-2.5-flash",
        validation_alias=AliasChoices("gemini_model_name", "gemini_model", "model_name"),
    )
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    default_timezone: str = "Asia/Karachi"

    # CORS Configuration for Next.js / Vercel frontend
    cors_origins: list[str] = Field(
        default=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3001",
        ],
        validation_alias=AliasChoices("cors_origins", "cors_origin", "allowed_origins"),
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("[") and value.endswith("]"):
                try:
                    return json.loads(value)
                except Exception:
                    pass
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
