"""HTTP boundary for catalog metadata and source-linked evidence-coverage candidates."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from evidenceos.application.use_cases.library import LibraryItem
from evidenceos.domain.entities.gaps import GapComparison
from evidenceos.domain.entities.library import LibraryMetadata, ReadingStatus
from evidenceos.domain.entities.literature import LiteratureFacet
from evidenceos.presentation.api.workspace_schemas import SavedLiteratureResponse


class LibraryMetadataRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ReadingStatus
    tags: list[str] = Field(max_length=8)


class LibraryMetadataResponse(BaseModel):
    entry_id: UUID
    status: ReadingStatus
    tags: list[str]
    updated_at: datetime

    @classmethod
    def from_entity(cls, entity: LibraryMetadata) -> "LibraryMetadataResponse":
        return cls(
            entry_id=entity.entry_id,
            status=entity.status,
            tags=list(entity.tags),
            updated_at=entity.updated_at,
        )


class LibraryItemResponse(BaseModel):
    entry: SavedLiteratureResponse
    metadata: LibraryMetadataResponse

    @classmethod
    def from_entity(cls, entity: LibraryItem) -> "LibraryItemResponse":
        return cls(
            entry=SavedLiteratureResponse.from_entity(entity.entry),
            metadata=LibraryMetadataResponse.from_entity(entity.metadata),
        )


class CompareGapsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry_ids: list[UUID] = Field(min_length=2, max_length=10)


class GroundedReferenceResponse(BaseModel):
    entry_id: UUID
    document_title: str
    locator: str
    quote: str
    interpretation: str


class CoverageCandidateResponse(BaseModel):
    facet: LiteratureFacet
    grounded_count: int
    total_count: int
    not_identified_entry_ids: list[UUID]
    rejected_entry_ids: list[UUID]
    references: list[GroundedReferenceResponse]
    recommendation: str


class GapComparisonResponse(BaseModel):
    project_id: UUID
    document_ids: list[UUID]
    candidates: list[CoverageCandidateResponse]
    caveat: str

    @classmethod
    def from_entity(cls, report: GapComparison) -> "GapComparisonResponse":
        return cls(
            project_id=report.project_id,
            document_ids=list(report.document_ids),
            candidates=[
                CoverageCandidateResponse(
                    facet=c.facet,
                    grounded_count=c.grounded_count,
                    total_count=c.total_count,
                    not_identified_entry_ids=list(c.not_identified_entry_ids),
                    rejected_entry_ids=list(c.rejected_entry_ids),
                    references=[
                        GroundedReferenceResponse(
                            entry_id=r.entry_id,
                            document_title=r.document_title,
                            locator=r.locator,
                            quote=r.quote,
                            interpretation=r.interpretation,
                        )
                        for r in c.references
                    ],
                    recommendation=c.recommendation,
                )
                for c in report.candidates
            ],
            caveat=report.caveat,
        )
