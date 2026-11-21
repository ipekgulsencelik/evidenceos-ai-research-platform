"""Provider-neutral contracts; no HTTP library is imported into the domain."""

from typing import Protocol

from evidenceos.domain.entities.academic import AcademicWork, CitationMetadata


class AcademicSearchProvider(Protocol):
    async def search(self, query: str, limit: int) -> tuple[AcademicWork, ...]: ...


class CitationMetadataProvider(Protocol):
    async def lookup(self, doi: str) -> CitationMetadata | None: ...
