"""Role-scoped project access regression tests with trusted test principals."""

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from evidenceos.application.use_cases.access import AssignProjectRole, EnforceProjectAccess
from evidenceos.application.use_cases.projects import CreateProject, CreateProjectCommand
from evidenceos.domain.entities.access import (
    Principal,
    ProjectAction,
    ProjectRole,
    role_allows,
    stable_subject_key,
)
from evidenceos.domain.entities.project import ResearchDomain, ResearchProject
from evidenceos.domain.errors import ProjectNotFound
from evidenceos.infrastructure.config import Settings
from evidenceos.presentation.api.app import create_app
from evidenceos.presentation.api.dependencies import get_uow_factory
from evidenceos.presentation.api.security import validate_service_credential
from tests.fakes import FakeAccessAuditRepository, FakeMembershipRepository, FakeUnitOfWork


def user(identifier: str) -> Principal:
    return Principal(stable_subject_key("https://idp.example", identifier), "oidc_user")


@pytest.mark.parametrize(
    ("role", "allowed_actions"),
    [
        (None, set()),
        (ProjectRole.VIEWER, {ProjectAction.READ}),
        (ProjectRole.REVIEWER, {ProjectAction.READ, ProjectAction.REVIEW}),
        (ProjectRole.EDITOR, {ProjectAction.READ, ProjectAction.WRITE, ProjectAction.REVIEW}),
        (ProjectRole.OWNER, set(ProjectAction)),
    ],
)
def test_explicit_role_matrix(
    role: ProjectRole | None, allowed_actions: set[ProjectAction],
) -> None:
    for action in ProjectAction:
        assert role_allows(role, action) == (action in allowed_actions)


def test_issuer_scoped_pseudonymous_keys() -> None:
    assert stable_subject_key("issuer-A", "alice") != stable_subject_key("issuer-B", "alice")
    assert stable_subject_key("issuer-A", "alice") != stable_subject_key("issuer-A", "bob")
    assert len(stable_subject_key("issuer-A", "alice")) == 64
    with pytest.raises(ValueError):
        stable_subject_key("", "alice")


@pytest.mark.asyncio
async def test_role_assignment_and_denied_access_are_audited() -> None:
    store: dict[UUID, ResearchProject] = {}
    memberships = FakeMembershipRepository()
    audit = FakeAccessAuditRepository()

    def factory() -> FakeUnitOfWork:
        return FakeUnitOfWork(store, memberships=memberships, access_audit=audit)

    alice, bob, charlie = user("alice"), user("bob"), user("charlie")
    project = await CreateProject(factory).execute(
        CreateProjectCommand("Isolated project", ResearchDomain.ACADEMIC),
        actor=alice,
    )
    assert await memberships.role_for(project.id, alice.key) is ProjectRole.OWNER
    assert await memberships.role_for(project.id, bob.key) is None

    with pytest.raises(ProjectNotFound):
        await EnforceProjectAccess(factory).execute(bob, project.id, ProjectAction.READ)
    await AssignProjectRole(factory).execute(alice, project.id, bob.key, ProjectRole.REVIEWER)
    await EnforceProjectAccess(factory).execute(bob, project.id, ProjectAction.READ)
    await EnforceProjectAccess(factory).execute(bob, project.id, ProjectAction.REVIEW)
    with pytest.raises(ProjectNotFound):
        await EnforceProjectAccess(factory).execute(bob, project.id, ProjectAction.WRITE)
    with pytest.raises(ProjectNotFound):
        await AssignProjectRole(factory).execute(
            bob, project.id, charlie.key, ProjectRole.OWNER
        )
    assert await memberships.role_for(project.id, charlie.key) is None
    assert [event.outcome for event in audit.events if event.action == "write"] == ["denied"]
    assert audit.events[-1].action == "membership.assign"
    assert audit.events[-1].outcome == "denied"


def test_routes_hide_other_users_projects_and_filter_listing() -> None:
    store: dict[UUID, ResearchProject] = {}
    memberships = FakeMembershipRepository()
    audit = FakeAccessAuditRepository()
    holder = {"principal": user("alice")}
    app = create_app(
        Settings(app_env="test", database_url="postgresql+asyncpg://u:p@localhost:5432/test")
    )

    def factory() -> FakeUnitOfWork:
        return FakeUnitOfWork(store, memberships=memberships, access_audit=audit)

    app.dependency_overrides[get_uow_factory] = lambda: factory
    # Bypass the trusted boundary in tests only; no identity header is accepted.
    app.dependency_overrides[validate_service_credential] = lambda: holder["principal"]

    with TestClient(app) as client:
        created = client.post(
            "/api/v1/projects", json={"title": "Alice project", "domain": "academic"}
        )
        assert created.status_code == 201, created.text
        project_id = created.json()["id"]
        assert client.get("/api/v1/projects").json()[0]["id"] == project_id

        legacy = ResearchProject.create("Unclaimed old project", ResearchDomain.ACADEMIC)
        store[legacy.id] = legacy
        assert all(row["id"] != str(legacy.id) for row in client.get("/api/v1/projects").json())

        holder["principal"] = user("bob")
        assert client.get("/api/v1/projects").json() == []
        assert client.get(f"/api/v1/projects/{project_id}").status_code == 404
        assert client.get(f"/api/v1/projects/{project_id}/library").status_code == 404
        assert client.post(
            f"/api/v1/projects/{project_id}/research-gaps", json={}
        ).status_code == 404
        assert client.get(f"/api/v1/projects/{project_id}/access-audit").status_code == 404

        holder["principal"] = user("alice")
        assert client.get(f"/api/v1/projects/{project_id}/access-audit").status_code == 200

    assert any(event.outcome == "denied" for event in audit.events)
