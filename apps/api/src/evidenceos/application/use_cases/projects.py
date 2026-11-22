"""Application services depend only on domain ports."""

from dataclasses import dataclass
from uuid import UUID

from evidenceos.domain.entities.access import (
    AccessDecisionEvent,
    Principal,
    ProjectMembership,
    ProjectRole,
)
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

    async def execute(
        self,
        command: CreateProjectCommand,
        actor: Principal | None = None,
        request_id: str = "",
    ) -> ResearchProject:
        project = ResearchProject.create(title=command.title, domain=command.domain)
        async with self._uow_factory() as uow:
            await uow.projects.add(project)
            if actor is not None:
                if not actor.is_operator:
                    await uow.memberships.upsert(
                        ProjectMembership.create(project.id, actor.key, ProjectRole.OWNER)
                    )
                await uow.access_audit.append(
                    AccessDecisionEvent.create(
                        actor.key, project.id, "project.create", "allowed", request_id
                    )
                )
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
