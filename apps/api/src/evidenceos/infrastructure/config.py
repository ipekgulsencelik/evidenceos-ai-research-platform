"""Validated, environment-based application configuration."""

from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="EVIDENCEOS_",
        env_file=".env",
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    security_mode: Literal["local", "service_token"] = "local"
    api_service_token: str | None = None
    database_url: str = Field(min_length=1)
    cors_origins: list[str] = Field(default_factory=list)
    openalex_api_key: str | None = None
    crossref_contact_email: str | None = None
    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-20b"
    research_timeout_seconds: float = Field(default=8.0, ge=1.0, le=30.0)

    @model_validator(mode="after")
    def validate_security(self) -> Self:
        """Never start in production with an unprotected API."""
        if self.app_env == "production" and self.security_mode != "service_token":
            raise ValueError("production requires service_token security mode")
        if self.security_mode == "service_token" and (
            self.api_service_token is None or len(self.api_service_token) < 32
        ):
            raise ValueError("service_token mode requires a token of at least 32 characters")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
