"""Library metadata operations; immutable evidence snapshots stay unchanged."""

import re
from dataclasses import dataclass
from uuid import UUID

from evidenceos.application.use_cases.workspace import (
    GetLiteratureAnalysis,
    ListLiteratureAnalyses,
)
from evidenceos.domain.entities.library import LibraryMetadata, ReadingStatus
from evidenceos.domain.entities.workspace import LiteratureEntry
from evidenceos.domain.errors import InvalidResearchWorkspace
from evidenceos.domain.ports.repositories import UnitOfWorkFactory

_TAG_PATTERN = re.compile(r"^[\w\- ]{1,32}$", re.UNICODE)


@dataclass(frozen=True, slots=True)
class LibraryItem:
    entry: LiteratureEntry
    metadata: LibraryMetadata


@dataclass(frozen=True, slots=True)
class UpdateCatalogCommand:
    project_id: UUID
    entry_id: UUID
    status: ReadingStatus
    tags: tuple[str, ...]


def validate_tags(tags: tuple[str, ...]) -> tuple[str, ...]:
    if len(tags) > 8:
        raise InvalidResearchWorkspace("At most 8 tags are allowed")
    clean: list[str] = []
    for tag in tags:
        stripped = tag.strip()
        if not _TAG_PATTERN.fullmatch(stripped):
            raise InvalidResearchWorkspace("Tags must be 1–32 letters, digits or spaces")
        if stripped.casefold() not in {item.casefold() for item in clean}:
            clean.append(stripped)
    return tuple(clean)


class UpdateLibraryMetadata:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, command: UpdateCatalogCommand) -> LibraryMetadata:
        tags = validate_tags(command.tags)
        # Enforce project scope before writing. Never alter the model's findings.
        await GetLiteratureAnalysis(self._uow_factory).execute(command.project_id, command.entry_id)
        metadata = LibraryMetadata.create(command.entry_id, command.status, tags)
        async with self._uow_factory() as uow:
            await uow.library.upsert(metadata)
            await uow.commit()
        return metadata


class ListLibraryItems:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(
        self,
        project_id: UUID,
        *,
        query: str = "",
        status: ReadingStatus | None = None,
        tag: str = "",
        limit: int = 100,
    ) -> list[LibraryItem]:
        if len(query) > 120 or len(tag) > 32:
            raise InvalidResearchWorkspace("Library filter is too long")
        # Bound this first-release local catalog to the newest 100 snapshots.
        entries = await ListLiteratureAnalyses(self._uow_factory).execute(project_id, limit=100)
        items: list[LibraryItem] = []
        async with self._uow_factory() as uow:
            for entry in entries:
                stored = await uow.library.get(entry.id)
                metadata = stored or LibraryMetadata.create(entry.id, ReadingStatus.TO_READ, ())
                if query and query.casefold() not in entry.profile.document_title.casefold():
                    continue
                if status is not None and metadata.status is not status:
                    continue
                if tag and tag.casefold() not in {t.casefold() for t in metadata.tags}:
                    continue
                items.append(LibraryItem(entry, metadata))
                if len(items) >= limit:
                    break
        return items
