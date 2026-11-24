"""Rate-limit configuration and authenticated FastAPI boundary regression."""

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from evidenceos.domain.entities.project import ResearchProject
from evidenceos.domain.ports.rate_limits import RateLimitDecision
from evidenceos.infrastructure.config import Settings
from evidenceos.presentation.api.app import create_app
from evidenceos.presentation.api.dependencies import get_uow_factory
from evidenceos.presentation.api.rate_limits import is_high_cost_request
from tests.fakes import FakeUnitOfWork

DATABASE = "postgresql+asyncpg://u:p@localhost:5432/test"
TOKEN = "rate-limit-service-token-01234567890123456789"
SECRET = "test-rate-limiter-password-with-high-entropy-123456"


class StubLimiter:
    def __init__(self, allowed: bool = True, failing: bool = False) -> None:
        self.allowed = allowed
        self.failing = failing
        self.calls: list[tuple[str, int, int, bool]] = []

    async def consume(
        self,
        principal_key: str,
        *,
        maximum: int,
        expensive_maximum: int,
        expensive: bool,
    ) -> RateLimitDecision:
        self.calls.append((principal_key, maximum, expensive_maximum, expensive))
        if self.failing:
            raise ConnectionError("secret connection details not for clients")
        return RateLimitDecision(allowed=self.allowed, retry_after_seconds=37)

    async def aclose(self) -> None:
        return None


def client_with_limiter(limiter: StubLimiter) -> TestClient:
    app = create_app(
        Settings(
            database_url=DATABASE,
            app_env="test",
            security_mode="service_token",
            api_service_token=TOKEN,
            rate_limit_enabled=True,
            rate_limit_redis_url="redis://redis.test:6379",
            rate_limit_redis_password=SECRET,
            rate_limit_requests_per_minute=2,
            rate_limit_expensive_per_minute=1,
        )
    )
    app.state.rate_limiter = limiter
    store: dict[UUID, ResearchProject] = {}
    app.dependency_overrides[get_uow_factory] = lambda: lambda: FakeUnitOfWork(store)
    return TestClient(app)


def test_limit_rejects_authenticated_requests_and_excludes_health() -> None:
    limiter = StubLimiter(allowed=False)
    client = client_with_limiter(limiter)
    auth = {"Authorization": "Bearer " + TOKEN}
    assert client.get("/api/v1/health/live").status_code == 200
    assert client.get("/api/v1/projects").status_code == 401
    assert limiter.calls == []
    response = client.get("/api/v1/projects", headers=auth)
    assert response.status_code == 429
    assert response.headers["retry-after"] == "37"
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"detail": "Too many requests"}
    assert len(limiter.calls) == 1
    assert limiter.calls[0][1:] == (2, 1, False)
    assert len(limiter.calls[0][0]) == 64
    assert TOKEN not in str(limiter.calls)


def test_storage_unavailable_fails_closed_without_leaking_internal_details() -> None:
    limiter = StubLimiter(failing=True)
    response = client_with_limiter(limiter).get(
        "/api/v1/projects",
        headers={"Authorization": "Bearer " + TOKEN},
    )
    assert response.status_code == 503
    assert response.headers["retry-after"] == "5"
    assert response.headers["cache-control"] == "no-store"
    assert "connection" not in str(response.json())
    assert TOKEN not in str(response.json())


@pytest.mark.parametrize(
    "method,path,expensive",
    [
        ("POST", "/api/v1/evidence/assess", True),
        ("POST", "/api/v1/documents/retrieve-passages", True),
        ("POST", "/api/v1/projects/123/literature/analyze-pdf", True),
        ("POST", "/api/v1/projects/123/semantic-gaps", True),
        ("PUT", "/api/v1/projects/123/methodology-review", True),
        ("GET", "/api/v1/projects/123/semantic-gaps", False),
        ("POST", "/api/v1/projects", False),
    ],
)
def test_expensive_policy(method: str, path: str, expensive: bool) -> None:
    assert is_high_cost_request(method, path) is expensive


def test_production_requires_shared_limiter_and_tls() -> None:
    common = dict(
        app_env="production",
        security_mode="service_token",
        api_service_token=TOKEN,
        database_url=DATABASE,
    )
    with pytest.raises(ValidationError):
        Settings.model_validate(common)
    with pytest.raises(ValidationError):
        Settings.model_validate(
            {
                **common,
                "rate_limit_enabled": True,
                "rate_limit_redis_url": "redis://redis.test:6379",
                "rate_limit_redis_password": SECRET,
            }
        )
    secure = Settings.model_validate(
        {
            **common,
            "rate_limit_enabled": True,
            "rate_limit_redis_url": "rediss://redis.test:6379",
            "rate_limit_redis_password": SECRET,
        }
    )
    assert secure.rate_limit_enabled is True


@pytest.mark.parametrize(
    "url",
    [
        "http://redis.test",
        "redis://user:pass@redis.test:6379",
        "rediss://redis.test:6379/3",
        "redis://redis.test:6379?unsafe=1",
        "redis://redis.test:6379#unsafe",
    ],
)
def test_rejects_unsafe_store_configuration(url: str) -> None:
    with pytest.raises(ValidationError):
        Settings(
            database_url=DATABASE,
            app_env="test",
            security_mode="local",
            rate_limit_enabled=True,
            rate_limit_redis_url=url,
            rate_limit_redis_password=SECRET,
        )
