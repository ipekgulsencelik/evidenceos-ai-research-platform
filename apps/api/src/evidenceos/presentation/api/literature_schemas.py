"""HTTP contracts: every extracted field carries a server-verified PDF locator."""

from pydantic import BaseModel

from evidenceos.domain.entities.literature import (
    FindingStatus,
    LiteratureFacet,
    LiteratureProfile,
)


class LiteratureFindingResponse(BaseModel):
    facet: LiteratureFacet
    status: FindingStatus
    value: str | None
    quote: str | None
    locator: str | None


class LiteratureProfileResponse(BaseModel):
    document_title: str
    sha256: str
    page_count: int
    text_page_count: int
    model: str
    findings: list[LiteratureFindingResponse]
    caveat: str

    @classmethod
    def from_entity(cls, value: LiteratureProfile) -> "LiteratureProfileResponse":
        return cls(
            document_title=value.document_title,
            sha256=value.sha256,
            page_count=value.page_count,
            text_page_count=value.text_page_count,
            model=value.model,
            findings=[
                LiteratureFindingResponse(
                    facet=field.facet,
                    status=field.status,
                    value=field.value,
                    quote=field.quote,
                    locator=field.locator,
                )
                for field in value.findings
            ],
            caveat=value.caveat,
        )
