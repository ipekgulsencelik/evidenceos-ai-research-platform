from uuid import UUID, uuid4

import pytest

from evidenceos.application.use_cases.projects import (
    CreateProject,
    CreateProjectCommand,
    GetProject,
)
from evidenceos.domain.entities.project import ResearchDomain, ResearchProject
from evidenceos.domain.errors import ProjectNotFound
from tests.fakes import FakeUnitOfWork


@pytest.mark.asyncio
async def test_create_then_get_project() -> None:
    store: dict[UUID, ResearchProject] = {}
    make_uow = lambda: FakeUnitOfWork(store)
    created = await CreateProject(make_uow).execute(
        CreateProjectCommand("My thesis", ResearchDomain.ACADEMIC)
    )
    loaded = await GetProject(make_uow).execute(created.id)
    assert loaded == created
    assert created.id in store


@pytest.mark.asyncio
async def test_get_missing_project_raises() -> None:
    make_uow = lambda: FakeUnitOfWork({})
    with pytest.raises(ProjectNotFound):
        await GetProject(make_uow).execute(uuid4())


@pytest.mark.asyncio
async def test_failed_uow_does_not_commit() -> None:
    store: dict[UUID, ResearchProject] = {}
    uow = FakeUnitOfWork(store)
    project = ResearchProject.create("Test project", ResearchDomain.LEGAL)
    with pytest.raises(RuntimeError, match="abort"):
        async with uow:
            await uow.projects.add(project)
            raise RuntimeError("abort")
    assert project.id not in store
    assert not uow.committed
