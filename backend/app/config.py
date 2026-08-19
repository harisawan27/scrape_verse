from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # The production source of truth must be Neon/PostgreSQL, never Space disk.
    database_url: str = "postgresql+psycopg://web_radar:replace-me@localhost:5432/web_radar"
    app_env: str = "development"
    log_level: str = "INFO"
    scheduler_poll_interval_seconds: float = 5.0
    scheduler_enabled: bool = False

    # Bright Data Scraper Studio Configuration
    bright_data_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("bright_data_api_key", "brightdata_api_key"),
    )
    bright_data_collector_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("bright_data_collector_id", "brightdata_collector_id"),
    )
    bright_data_base_url: str = "https://api.brightdata.com"
    bright_data_poll_timeout_seconds: float = 60.0
    bright_data_poll_interval_seconds: float = 2.0

    # Gemini LLM Planner Configuration
    gemini_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("gemini_api_key", "google_api_key", "gemini_key", "gemeni_key", "gemeni_api_key"),
    )
    gemini_model_name: str = Field(
        default="gemini-2.5-flash",
        validation_alias=AliasChoices("gemini_model_name", "gemini_model", "model_name"),
    )


    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    default_timezone: str = "Asia/Karachi"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")






@lru_cache
def get_settings() -> Settings:
    return Settings()
