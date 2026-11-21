"""Application services depend only on domain ports."""

from dataclasses import dataclass
from uuid import UUID

from evidenceos.domain.entities.project import ResearchDomain, ResearchProject
from evidenceos.domain.errors import ProjectNotFound
from evidenceos.domain.ports.repositories import UnitOfWorkFactory


@dataclass(frozen=True, slots=True)
class CreateProjectCommand:
    title: str
    domain: ResearchDomain


class CreateProject:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, command: CreateProjectCommand) -> ResearchProject:
        project = ResearchProject.create(title=command.title, domain=command.domain)
        async with self._uow_factory() as uow:
            await uow.projects.add(project)
            await uow.commit()
        return project


class GetProject:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, project_id: UUID) -> ResearchProject:
        async with self._uow_factory() as uow:
            project = await uow.projects.get(project_id)
        if project is None:
            raise ProjectNotFound(f"project '{project_id}' not found")
        return project
