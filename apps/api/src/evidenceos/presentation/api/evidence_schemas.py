"""Bounded HTTP contracts for user-supplied evidence excerpts."""

from pydantic import BaseModel, ConfigDict, Field

from evidenceos.domain.entities.evidence import EvidenceReport, EvidenceSource, EvidenceVerdict


class EvidenceSourceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source_id: str = Field(min_length=1, max_length=150)
    title: str = Field(min_length=3, max_length=300)
    passage: str = Field(min_length=30, max_length=4000)
    locator: str | None = Field(default=None, max_length=200)

    def to_entity(self) -> EvidenceSource:
        return EvidenceSource(self.source_id, self.title, self.passage, self.locator)


class AssessEvidenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    claim: str = Field(min_length=10, max_length=500)
    sources: list[EvidenceSourceRequest] = Field(min_length=1, max_length=3)


class EvidenceRowResponse(BaseModel):
    source_id: str
    title: str
    locator: str | None
    verdict: EvidenceVerdict
    quote: str | None
    explanation: str


class EvidenceReportResponse(BaseModel):
    claim: str
    model: str
    rows: list[EvidenceRowResponse]
    caveat: str = (
        "Model assessment of user-supplied passages only; does not verify the original "
        "publication, scientific truth, or applicability of findings. Human review required."
    )

    @classmethod
    def from_entity(cls, value: EvidenceReport) -> "EvidenceReportResponse":
        return cls(
            claim=value.claim,
            model=value.model,
            rows=[
                EvidenceRowResponse(
                    source_id=row.source_id,
                    title=row.title,
                    locator=row.locator,
                    verdict=row.verdict,
                    quote=row.quote,
                    explanation=row.explanation,
                )
                for row in value.rows
            ],
        )
