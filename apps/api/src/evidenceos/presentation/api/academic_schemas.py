"""Academic research public API contracts, separate from domain entities."""

from pydantic import BaseModel, ConfigDict, Field

from evidenceos.domain.entities.academic import AcademicWork, CitationCheck, CitationStatus


class AcademicWorkResponse(BaseModel):
    source_id: str
    title: str
    doi: str | None
    publication_year: int | None
    authors: list[str]
    source_url: str

    @classmethod
    def from_entity(cls, entity: AcademicWork) -> "AcademicWorkResponse":
        return cls(
            source_id=entity.source_id,
            title=entity.title,
            doi=entity.doi,
            publication_year=entity.publication_year,
            authors=list(entity.authors),
            source_url=entity.source_url,
        )


class VerifyCitationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    doi: str = Field(min_length=7, max_length=300)
    expected_title: str | None = Field(default=None, max_length=500)


class CitationMetadataResponse(BaseModel):
    doi: str
    title: str
    publication_year: int | None
    source_url: str


class CitationCheckResponse(BaseModel):
    doi: str
    status: CitationStatus
    metadata: CitationMetadataResponse | None

    @classmethod
    def from_entity(cls, value: CitationCheck) -> "CitationCheckResponse":
        return cls.model_validate(
            {"doi": value.doi, "status": value.status, "metadata": value.metadata},
            from_attributes=True,
        )
