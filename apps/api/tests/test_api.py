from collections.abc import AsyncIterator, Iterator
from typing import cast
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.sql.elements import TextClause

from evidenceos.domain.entities.project import ResearchProject
from evidenceos.infrastructure.config import Settings
from evidenceos.presentation.api.app import create_app
from evidenceos.presentation.api.dependencies import get_db_session, get_uow_factory
from tests.fakes import FakeUnitOfWork


@pytest.fixture
def client() -> Iterator[TestClient]:
    settings = Settings(
        app_env="test", database_url="postgresql+asyncpg://u:p@localhost:5432/test"
    )
    app = create_app(settings)
    store: dict[UUID, ResearchProject] = {}
    app.dependency_overrides[get_uow_factory] = lambda: lambda: FakeUnitOfWork(store)
    test_client = TestClient(app)
    yield test_client
    test_client.close()
    app.dependency_overrides.clear()


def test_live_health(client: TestClient) -> None:
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}
    assert UUID(response.headers["X-Request-ID"])


def test_create_and_read_project(client: TestClient) -> None:
    created = client.post(
        "/api/v1/projects", json={"title": "  Adolescent AI research  ", "domain": "academic"}
    )
    assert created.status_code == 201
    data = created.json()
    assert data["title"] == "Adolescent AI research"
    assert data["domain"] == "academic"
    assert UUID(data["id"])
    fetched = client.get(f"/api/v1/projects/{data['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == data


def test_missing_project_returns_404(client: TestClient) -> None:
    response = client.get("/api/v1/projects/eb630827-a024-4080-9cba-f00284f54e68")
    assert response.status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "x", "domain": "academic"},
        {"title": "Valid project", "domain": "unrecognized"},
        {"title": "Valid project", "domain": "legal", "extra": "not allowed"},
    ],
)
def test_rejects_invalid_payload(client: TestClient, payload: dict[str, str]) -> None:
    response = client.post("/api/v1/projects", json=payload)
    assert response.status_code == 422


class FakeDbSession:
    def __init__(self, *, fails: bool = False) -> None:
        self.fails = fails

    async def execute(self, statement: TextClause) -> None:
        if self.fails:
            raise RuntimeError("db unavailable")


@pytest.mark.parametrize("fails,status", [(False, 200), (True, 503)])
def test_ready_health(client: TestClient, fails: bool, status: int) -> None:
    app = cast(FastAPI, client.app)

    async def fake_db() -> AsyncIterator[FakeDbSession]:
        yield FakeDbSession(fails=fails)

    app.dependency_overrides[get_db_session] = fake_db
    response = client.get("/api/v1/health/ready")
    assert response.status_code == status
    if fails:
        assert "db unavailable" not in response.text
        assert response.json() == {"detail": "database unavailable"}
    else:
        assert response.json() == {"status": "ready"}
