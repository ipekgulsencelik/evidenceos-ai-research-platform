"""Public API types for private, transient PDF passage retrieval."""

from pydantic import BaseModel

from evidenceos.domain.entities.document import DocumentReview


class CandidatePassageResponse(BaseModel):
    source_id: str
    title: str
    locator: str
    passage: str
    matched_terms: list[str]
    lexical_score: float


class DocumentReviewResponse(BaseModel):
    title: str
    sha256: str
    page_count: int
    text_page_count: int
    passages: list[CandidatePassageResponse]
    caveat: str

    @classmethod
    def from_entity(cls, value: DocumentReview) -> "DocumentReviewResponse":
        return cls(
            title=value.title,
            sha256=value.sha256,
            page_count=value.page_count,
            text_page_count=value.text_page_count,
            passages=[
                CandidatePassageResponse(
                    source_id=item.source_id,
                    title=item.title,
                    locator=item.locator,
                    passage=item.passage,
                    matched_terms=list(item.matched_terms),
                    lexical_score=item.lexical_score,
                )
                for item in value.passages
            ],
            caveat=value.caveat,
        )
