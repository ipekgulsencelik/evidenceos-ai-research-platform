"""API contracts for project-scoped literature records and reviewer revisions."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from evidenceos.domain.entities.literature import LiteratureFacet
from evidenceos.domain.entities.workspace import LiteratureEntry, ReviewRevision
from evidenceos.presentation.api.literature_schemas import LiteratureProfileResponse


class SavedLiteratureResponse(BaseModel):
    id: UUID
    project_id: UUID
    created_at: datetime
    profile: LiteratureProfileResponse

    @classmethod
    def from_entity(cls, entry: LiteratureEntry) -> "SavedLiteratureResponse":
        return cls(
            id=entry.id,
            project_id=entry.project_id,
            created_at=entry.created_at,
            profile=LiteratureProfileResponse.from_entity(entry.profile),
        )


class ReviewRevisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    facet: LiteratureFacet
    corrected_value: str = Field(default="", max_length=500)
    note: str = Field(default="", max_length=1000)
    reviewed: bool = False


class ReviewRevisionResponse(BaseModel):
    id: UUID
    entry_id: UUID
    facet: LiteratureFacet
    corrected_value: str
    note: str
    reviewed: bool
    created_at: datetime

    @classmethod
    def from_entity(cls, review: ReviewRevision) -> "ReviewRevisionResponse":
        return cls(
            id=review.id,
            entry_id=review.entry_id,
            facet=review.facet,
            corrected_value=review.corrected_value,
            note=review.note,
            reviewed=review.reviewed,
            created_at=review.created_at,
        )
