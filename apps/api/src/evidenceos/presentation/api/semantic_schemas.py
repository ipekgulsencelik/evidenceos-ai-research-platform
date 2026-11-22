"""Typed HTTP contract for provisional, quote-linked AI comparison outputs."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from evidenceos.domain.entities.semantic import (
    ComparisonKind,
    SemanticDimension,
    SemanticGapReport,
)


class SemanticComparisonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry_ids: list[UUID] = Field(min_length=2, max_length=10)
    consent_to_share_quotes: bool = False


class SemanticReferenceResponse(BaseModel):
    reference_id: str
    entry_id: UUID
    document_title: str
    dimension: SemanticDimension
    locator: str
    quote: str


class SemanticCandidateResponse(BaseModel):
    dimension: SemanticDimension
    kind: ComparisonKind
    summary: str
    research_question: str
    references: list[SemanticReferenceResponse]


class SemanticGapReportResponse(BaseModel):
    project_id: UUID
    document_ids: list[UUID]
    model: str
    candidates: list[SemanticCandidateResponse]
    skipped_candidates: int
    insufficient_dimensions: list[SemanticDimension]
    caveat: str

    @classmethod
    def from_entity(cls, report: SemanticGapReport) -> "SemanticGapReportResponse":
        return cls(
            project_id=report.project_id,
            document_ids=list(report.document_ids),
            model=report.model,
            candidates=[
                SemanticCandidateResponse(
                    dimension=item.dimension,
                    kind=item.kind,
                    summary=item.summary,
                    research_question=item.research_question,
                    references=[
                        SemanticReferenceResponse(
                            reference_id=source.reference_id,
                            entry_id=source.entry_id,
                            document_title=source.document_title,
                            dimension=source.dimension,
                            locator=source.locator,
                            quote=source.quote,
                        )
                        for source in item.references
                    ],
                )
                for item in report.candidates
            ],
            skipped_candidates=report.skipped_candidates,
            insufficient_dimensions=list(report.insufficient_dimensions),
            caveat=report.caveat,
        )
