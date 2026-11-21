"""Validated, environment-based application configuration."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="EVIDENCEOS_",
        env_file=".env",
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    database_url: str = Field(min_length=1)
    cors_origins: list[str] = Field(default_factory=list)
    openalex_api_key: str | None = None
    crossref_contact_email: str | None = None
    research_timeout_seconds: float = Field(default=8.0, ge=1.0, le=30.0)


@lru_cache
def get_settings() -> Settings:
    return Settings()
