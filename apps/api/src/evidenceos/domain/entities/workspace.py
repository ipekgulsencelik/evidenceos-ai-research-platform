"""Persistent, project-scoped literature snapshots and append-only reviewer revisions."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from evidenceos.domain.entities.literature import LiteratureFacet, LiteratureProfile


@dataclass(frozen=True, slots=True)
class LiteratureEntry:
    id: UUID
    project_id: UUID
    profile: LiteratureProfile
    created_at: datetime

    @classmethod
    def create(cls, project_id: UUID, profile: LiteratureProfile) -> "LiteratureEntry":
        return cls(uuid4(), project_id, profile, datetime.now(UTC))


@dataclass(frozen=True, slots=True)
class ReviewRevision:
    id: UUID
    entry_id: UUID
    facet: LiteratureFacet
    corrected_value: str
    note: str
    reviewed: bool
    created_at: datetime

    @classmethod
    def create(
        cls,
        entry_id: UUID,
        facet: LiteratureFacet,
        corrected_value: str,
        note: str,
        reviewed: bool,
    ) -> "ReviewRevision":
        return cls(
            id=uuid4(),
            entry_id=entry_id,
            facet=facet,
            corrected_value=corrected_value,
            note=note,
            reviewed=reviewed,
            created_at=datetime.now(UTC),
        )
