"""Append-only repository port for human reporting and concern reviews."""

from typing import Protocol
from uuid import UUID

from evidenceos.domain.entities.quality import QualityDimension, QualityReviewRevision


class QualityReviewRepository(Protocol):
    async def add(self, revision: QualityReviewRevision) -> None: ...

    async def latest(
        self, entry_id: UUID, dimension: QualityDimension
    ) -> QualityReviewRevision | None: ...

    async def history(self, entry_id: UUID, *, limit: int = 100) -> list[QualityReviewRevision]: ...
