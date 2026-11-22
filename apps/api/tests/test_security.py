"""Protected service boundary regression tests; no external database required."""

import logging
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from evidenceos.domain.entities.project import ResearchProject
from evidenceos.infrastructure.config import Settings
from evidenceos.presentation.api.app import create_app
from evidenceos.presentation.api.dependencies import get_uow_factory
from tests.fakes import FakeUnitOfWork

DATABASE = "postgresql+asyncpg://u:p@localhost:5432/test"
TOKEN = "security-test-token-with-adequate-entropy-0123456789"


def secured_client(*, environment: str = "test") -> TestClient:
    settings = Settings(
        app_env=environment,
        database_url=DATABASE,
        security_mode="service_token",
        api_service_token=TOKEN,
    )
    app = create_app(settings)
    store: dict[UUID, ResearchProject] = {}
    app.dependency_overrides[get_uow_factory] = lambda: lambda: FakeUnitOfWork(store)
    return TestClient(app)


@pytest.mark.parametrize(
    "setting",
    [
        {"app_env": "production", "security_mode": "local"},
        {"app_env": "production", "security_mode": "service_token", "api_service_token": None},
        {"app_env": "development", "security_mode": "service_token", "api_service_token": "weak"},
    ],
)
def test_security_configuration_fails_closed(setting: dict[str, str | None]) -> None:
    with pytest.raises(ValidationError):
        Settings(database_url=DATABASE, **setting)  # type: ignore[arg-type]


def test_service_token_is_not_required_for_local_development() -> None:
    settings = Settings(database_url=DATABASE, app_env="test", security_mode="local")
    app = create_app(settings)
    store: dict[UUID, ResearchProject] = {}
    app.dependency_overrides[get_uow_factory] = lambda: lambda: FakeUnitOfWork(store)
    response = TestClient(app).get("/api/v1/projects")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("GET", "/api/v1/projects", None),
        ("POST", "/api/v1/projects", {"title": "Secure project", "domain": "academic"}),
        ("GET", "/api/v1/academic/works?query=research", None),
        ("GET", "/api/v1/projects/00000000-0000-4000-8000-000000000000", None),
        ("GET", "/api/v1/projects/00000000-0000-4000-8000-000000000000/literature", None),
    ],
)
def test_every_research_route_rejects_anonymous_requests(
    method: str, path: str, body: dict[str, str] | None
) -> None:
    client = secured_client()
    response = client.request(method, path, json=body)
    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "credential",
    ["", "Bearer bad-token", "Basic dGVzdDpzZWNyZXQ=", "Bearer ", "Bearer " + TOKEN + " "],
)
def test_rejects_wrong_or_malformed_credentials(credential: str) -> None:
    client = secured_client()
    headers = {"Authorization": credential} if credential else {}
    assert client.get("/api/v1/projects", headers=headers).status_code == 401


def test_valid_token_accesses_project_routes_and_health_is_public() -> None:
    client = secured_client(environment="production")
    assert client.get("/api/v1/health/live").status_code == 200
    assert client.get("/api/v1/projects").status_code == 401
    headers = {"Authorization": "Bearer " + TOKEN}
    created = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"title": "Protected workspace", "domain": "academic"},
    )
    assert created.status_code == 201
    project_id = created.json()["id"]
    assert client.get("/api/v1/projects", headers=headers).json()[0]["id"] == project_id
    assert client.get(f"/api/v1/projects/{project_id}", headers=headers).status_code == 200


def test_failed_authentication_does_not_log_credentials(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = secured_client()
    with caplog.at_level(logging.WARNING):
        result = client.get("/api/v1/projects", headers={"Authorization": "Bearer " + TOKEN + "x"})
    assert result.status_code == 401
    assert "security.auth_denied" in caplog.text
    assert TOKEN not in caplog.text
