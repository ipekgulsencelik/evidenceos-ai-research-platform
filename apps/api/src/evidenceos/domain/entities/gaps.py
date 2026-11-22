"""Transparent coverage candidates; never claims a genuine research gap."""

from dataclasses import dataclass
from uuid import UUID

from evidenceos.domain.entities.literature import LiteratureFacet


@dataclass(frozen=True, slots=True)
class GroundedReference:
    entry_id: UUID
    document_title: str
    locator: str
    quote: str
    interpretation: str


@dataclass(frozen=True, slots=True)
class CoverageCandidate:
    facet: LiteratureFacet
    grounded_count: int
    total_count: int
    not_identified_entry_ids: tuple[UUID, ...]
    rejected_entry_ids: tuple[UUID, ...]
    references: tuple[GroundedReference, ...]
    recommendation: str


@dataclass(frozen=True, slots=True)
class GapComparison:
    project_id: UUID
    document_ids: tuple[UUID, ...]
    candidates: tuple[CoverageCandidate, ...]
    caveat: str
