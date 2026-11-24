"""No-secret structured request telemetry tests: no external database required."""

import json
from collections.abc import AsyncIterator
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from evidenceos.domain.entities.project import ResearchProject
from evidenceos.infrastructure.config import Settings
from evidenceos.presentation.api import observability
from evidenceos.presentation.api.app import create_app
from evidenceos.presentation.api.dependencies import get_db_session, get_uow_factory
from tests.fakes import FakeUnitOfWork

DB = "postgresql+asyncpg://u:p@localhost:5432/test"
SECRET = "private-access-token-do-not-log-0123456789"


@pytest.fixture
def events(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    collected: list[dict[str, object]] = []

    def capture(_format: str, payload: str) -> None:
        event = json.loads(payload)
        assert isinstance(event, dict)
        collected.append(event)

    monkeypatch.setattr(observability.logger, "info", capture)
    return collected


@pytest.fixture
def app() -> FastAPI:
    instance = create_app(Settings(app_env="test", database_url=DB))
    store: dict[UUID, ResearchProject] = {}
    instance.dependency_overrides[get_uow_factory] = lambda: lambda: FakeUnitOfWork(store)
    return instance


def test_known_route_logs_whitelisted_fields_and_server_generated_id(
    app: FastAPI, events: list[dict[str, object]]
) -> None:
    client = TestClient(app)
    response = client.get(
        "/api/v1/projects?search=secret-project-PII-123",
        headers={
            "Authorization": "Bearer " + SECRET,
            "Cookie": "eos_session=private-cookie-456",
            "X-Request-ID": "attacker-forged-id",
            "X-Forwarded-For": "198.51.100.25",
        },
    )
    assert response.status_code == 200
    request_id = response.headers["X-Request-ID"]
    assert request_id != "attacker-forged-id"
    assert UUID(request_id)
    assert len(events) == 1
    assert events[0] == {
        "event": "http.request.completed",
        "request_id": request_id,
        "method": "GET",
        "route_group": "projects",
        "status_code": 200,
        "duration_ms": events[0]["duration_ms"],
    }
    assert isinstance(events[0]["duration_ms"], int)
    assert events[0]["duration_ms"] >= 0
    emitted = json.dumps(events)
    for sensitive in (
        SECRET,
        "secret-project-PII-123",
        "private-cookie-456",
        "attacker-forged-id",
        "198.51.100.25",
        "/api/v1/projects?",
    ):
        assert sensitive not in emitted


def test_unauthorized_and_unmatched_requests_emit_safe_bounded_events(
    events: list[dict[str, object]],
) -> None:
    client = TestClient(
        create_app(
            Settings(
                app_env="test",
                database_url=DB,
                security_mode="service_token",
                api_service_token=SECRET,
            )
        )
    )
    rejected = client.get(
        "/api/v1/projects?jwt=top-secret", headers={"Authorization": "Bearer bad"}
    )
    assert rejected.status_code == 401
    unknown = client.get("/secret-path-with-user-identity-012345")
    assert unknown.status_code == 404
    assert [e["status_code"] for e in events] == [401, 404]
    assert [e["route_group"] for e in events] == ["projects", "unmatched"]
    assert "top-secret" not in json.dumps(events)
    assert "secret-path-with-user-identity" not in json.dumps(events)


def test_healthy_liveness_is_suppressed_but_failed_health_is_recorded(
    app: FastAPI, events: list[dict[str, object]]
) -> None:
    client = TestClient(app)
    assert client.get("/api/v1/health/live").status_code == 200
    assert events == []

    # A failed readiness DB query should be logged by status, never by
    # raw connection strings or exception details.
    class BrokenSession:
        async def execute(self, _statement: object) -> None:
            raise RuntimeError("private database details must never be logged")

    async def broken_db() -> AsyncIterator[BrokenSession]:
        yield BrokenSession()

    app.dependency_overrides[get_db_session] = broken_db
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert len(events) == 1
    assert events[0]["route_group"] == "health"
    assert events[0]["status_code"] == 503
    assert "private database details" not in json.dumps(events)


def test_unhandled_exception_records_500_without_exception_content(
    app: FastAPI, events: list[dict[str, object]]
) -> None:
    @app.get("/unhandled-debug")
    def raise_failure() -> None:
        raise RuntimeError("password=never-log-this-exception")

    response = TestClient(app, raise_server_exceptions=False).get("/unhandled-debug")
    assert response.status_code == 500
    assert events[-1]["status_code"] == 500
    assert events[-1]["route_group"] == "other"
    assert "never-log-this-exception" not in json.dumps(events)
