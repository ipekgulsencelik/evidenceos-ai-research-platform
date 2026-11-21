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


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # injected by environment
