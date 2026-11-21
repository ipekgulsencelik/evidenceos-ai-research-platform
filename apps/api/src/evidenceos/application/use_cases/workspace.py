"""Project-scoped literature write/read and audit history; uses domain-only ports."""

from dataclasses import dataclass
from uuid import UUID

from evidenceos.domain.entities.literature import LiteratureFacet, LiteratureProfile
from evidenceos.domain.entities.project import ResearchDomain, ResearchProject
from evidenceos.domain.entities.workspace import LiteratureEntry, ReviewRevision
from evidenceos.domain.errors import (
    InvalidResearchWorkspace,
    LiteratureEntryNotFound,
    ProjectNotFound,
)
from evidenceos.domain.ports.repositories import UnitOfWorkFactory


async def _require_project(uow_factory: UnitOfWorkFactory, project_id: UUID) -> None:
    async with uow_factory() as uow:
        project = await uow.projects.get(project_id)
    if project is None:
        raise ProjectNotFound(f"project '{project_id}' not found")
    if project.domain is not ResearchDomain.ACADEMIC:
        raise InvalidResearchWorkspace("Literature workspace requires an academic project")


class ListResearchProjects:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, *, limit: int = 50) -> list[ResearchProject]:
        async with self._uow_factory() as uow:
            return await uow.projects.list_recent(limit=limit)


class SaveLiteratureAnalysis:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, project_id: UUID, profile: LiteratureProfile) -> LiteratureEntry:
        entry = LiteratureEntry.create(project_id, profile)
        async with self._uow_factory() as uow:
            project = await uow.projects.get(project_id)
            if project is None:
                raise ProjectNotFound(f"project '{project_id}' not found")
            if project.domain is not ResearchDomain.ACADEMIC:
                raise InvalidResearchWorkspace("Literature workspace requires an academic project")
            await uow.literature.add(entry)
            await uow.commit()
        return entry


class ListLiteratureAnalyses:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, project_id: UUID, *, limit: int = 20) -> list[LiteratureEntry]:
        await _require_project(self._uow_factory, project_id)
        async with self._uow_factory() as uow:
            return await uow.literature.list_for_project(project_id, limit=limit)


class GetLiteratureAnalysis:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, project_id: UUID, entry_id: UUID) -> LiteratureEntry:
        await _require_project(self._uow_factory, project_id)
        async with self._uow_factory() as uow:
            entry = await uow.literature.get(entry_id)
        if entry is None or entry.project_id != project_id:
            raise LiteratureEntryNotFound("Literature entry not found in this project")
        return entry


@dataclass(frozen=True, slots=True)
class SaveReviewCommand:
    project_id: UUID
    entry_id: UUID
    facet: LiteratureFacet
    corrected_value: str
    note: str
    reviewed: bool


class SaveReviewRevision:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, command: SaveReviewCommand) -> ReviewRevision:
        if len(command.corrected_value) > 500 or len(command.note) > 1000:
            raise InvalidResearchWorkspace("Review note exceeds the allowed length")
        revision = ReviewRevision.create(
            command.entry_id,
            command.facet,
            command.corrected_value,
            command.note,
            command.reviewed,
        )
        async with self._uow_factory() as uow:
            project = await uow.projects.get(command.project_id)
            if project is None:
                raise ProjectNotFound(f"project '{command.project_id}' not found")
            if project.domain is not ResearchDomain.ACADEMIC:
                raise InvalidResearchWorkspace("Literature workspace requires an academic project")
            entry = await uow.literature.get(command.entry_id)
            if entry is None or entry.project_id != command.project_id:
                raise LiteratureEntryNotFound("Literature entry not found in this project")
            await uow.literature.add_review(revision)
            await uow.commit()
        return revision


class ListReviewRevisions:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(
        self, project_id: UUID, entry_id: UUID, *, limit: int = 100
    ) -> list[ReviewRevision]:
        await GetLiteratureAnalysis(self._uow_factory).execute(project_id, entry_id)
        async with self._uow_factory() as uow:
            return await uow.literature.list_reviews(entry_id, limit=limit)
