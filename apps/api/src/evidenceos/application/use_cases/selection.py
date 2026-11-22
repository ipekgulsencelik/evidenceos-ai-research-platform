"""Bounded and project-scoped source selection shared by comparison use cases."""

from uuid import UUID

from evidenceos.application.use_cases.workspace import _require_project
from evidenceos.domain.entities.workspace import LiteratureEntry
from evidenceos.domain.errors import InvalidResearchWorkspace, LiteratureEntryNotFound
from evidenceos.domain.ports.repositories import UnitOfWorkFactory


async def load_distinct_studies(
    uow_factory: UnitOfWorkFactory,
    project_id: UUID,
    entry_ids: tuple[UUID, ...],
) -> tuple[LiteratureEntry, ...]:
    if not 2 <= len(entry_ids) <= 10 or len(set(entry_ids)) != len(entry_ids):
        raise InvalidResearchWorkspace("Select 2–10 distinct saved analyses")
    await _require_project(uow_factory, project_id)
    async with uow_factory() as uow:
        entries = [await uow.literature.get(entry_id) for entry_id in entry_ids]
    if any(entry is None or entry.project_id != project_id for entry in entries):
        raise LiteratureEntryNotFound("A selected analysis is not in this project")
    validated = tuple(entry for entry in entries if entry is not None)
    if len({entry.profile.sha256 for entry in validated}) != len(validated):
        raise InvalidResearchWorkspace(
            "Select analyses of different PDFs, not repeated snapshots of one PDF"
        )
    return validated
