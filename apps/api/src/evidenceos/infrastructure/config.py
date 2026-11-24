"""Validated, environment-based application configuration."""

from functools import lru_cache
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="EVIDENCEOS_",
        env_file=".env",
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    security_mode: Literal["local", "service_token", "oidc"] = "local"
    api_service_token: str | None = None
    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_jwks_url: str | None = None
    database_url: str = Field(min_length=1)
    cors_origins: list[str] = Field(default_factory=list)
    openalex_api_key: str | None = None
    crossref_contact_email: str | None = None
    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-20b"
    research_timeout_seconds: float = Field(default=8.0, ge=1.0, le=30.0)
    rate_limit_enabled: bool = False
    rate_limit_redis_url: str | None = None
    rate_limit_redis_password: str | None = None
    rate_limit_requests_per_minute: int = Field(default=120, ge=1, le=10000)
    rate_limit_expensive_per_minute: int = Field(default=12, ge=1, le=10000)

    @model_validator(mode="after")
    def validate_security(self) -> Self:
        """Never start in production with an unprotected API."""
        if self.app_env == "production" and self.security_mode == "local":
            raise ValueError("production requires authenticated security mode")
        if self.security_mode == "service_token" and (
            self.api_service_token is None or len(self.api_service_token) < 32
        ):
            raise ValueError("service_token mode requires a token of at least 32 characters")
        if self.app_env == "production" and not self.rate_limit_enabled:
            raise ValueError("production requires distributed API rate limiting")
        if self.rate_limit_enabled:
            if not self.rate_limit_redis_url or not self.rate_limit_redis_password:
                raise ValueError("rate limiting requires Redis URL and password")
            if not 32 <= len(self.rate_limit_redis_password) <= 512:
                raise ValueError("rate limiting requires a strong Redis password")
            parsed_redis = urlsplit(self.rate_limit_redis_url)
            if (
                parsed_redis.scheme not in {"redis", "rediss"}
                or not parsed_redis.hostname
                or parsed_redis.username is not None
                or parsed_redis.password is not None
                or parsed_redis.query
                or parsed_redis.fragment
                or parsed_redis.path not in {"", "/"}
                or len(self.rate_limit_redis_url) > 2048
                or (self.app_env == "production" and parsed_redis.scheme != "rediss")
            ):
                raise ValueError("rate limiter needs a trusted Redis endpoint; TLS in production")
        if self.security_mode == "oidc":
            if not all((self.oidc_issuer, self.oidc_audience, self.oidc_jwks_url)):
                raise ValueError("oidc requires issuer, API audience, and trusted JWKS URL")
            if len(self.oidc_audience or "") > 256:
                raise ValueError("invalid OIDC API audience")
            for url in (self.oidc_issuer, self.oidc_jwks_url):
                parsed = urlsplit(url or "")
                if (
                    parsed.scheme != "https"
                    or not parsed.hostname
                    or parsed.username is not None
                    or parsed.password is not None
                    or parsed.query
                    or parsed.fragment
                    or len(url or "") > 2048
                ):
                    raise ValueError("OIDC endpoints must be trusted HTTPS URLs")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
