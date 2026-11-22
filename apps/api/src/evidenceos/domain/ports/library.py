"""Interface for reading and writing project-scoped catalog metadata."""

from typing import Protocol
from uuid import UUID

from evidenceos.domain.entities.library import LibraryMetadata


class LibraryRepository(Protocol):
    async def get(self, entry_id: UUID) -> LibraryMetadata | None: ...

    async def upsert(self, metadata: LibraryMetadata) -> None: ...
