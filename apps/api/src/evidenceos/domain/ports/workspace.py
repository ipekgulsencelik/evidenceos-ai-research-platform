"""Literature persistence port independent of SQLAlchemy."""

from typing import Protocol
from uuid import UUID

from evidenceos.domain.entities.workspace import LiteratureEntry, ReviewRevision


class LiteratureRepository(Protocol):
    async def add(self, entry: LiteratureEntry) -> None: ...

    async def get(self, entry_id: UUID) -> LiteratureEntry | None: ...

    async def list_for_project(
        self, project_id: UUID, *, limit: int = 20
    ) -> list[LiteratureEntry]: ...

    async def add_review(self, revision: ReviewRevision) -> None: ...

    async def list_reviews(self, entry_id: UUID, *, limit: int = 100) -> list[ReviewRevision]: ...
