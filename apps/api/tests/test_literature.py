"""Research-content extraction tests; mocked Groq and no real outbound AI requests."""

import json
from collections.abc import Iterator

import httpx
import pytest
from fastapi.testclient import TestClient

from evidenceos.application.use_cases.literature import (
    ExtractLiteratureProfile,
    collect_snippets,
)
from evidenceos.domain.entities.document import DocumentPage, ExtractedDocument
from evidenceos.domain.entities.literature import (
    FACET_ORDER,
    FindingStatus,
    LiteratureFacet,
    LiteratureRejectionReason,
    LiteratureSnippet,
    ProposedFinding,
)
from evidenceos.infrastructure.config import Settings
from evidenceos.infrastructure.providers.groq_evidence import (
    EvidenceProviderFailure,
    EvidenceProviderUnavailable,
)
from evidenceos.infrastructure.providers.groq_literature import GroqLiteratureAnalyst
from evidenceos.presentation.api.app import create_app
from evidenceos.presentation.api.routes.literature import (
    get_literature_analyst,
    get_pdf_extractor,
)

type SourceSnippets = tuple[LiteratureSnippet, ...]


DOC = ExtractedDocument(
    "Test paper.pdf",
    "abcdef1234567890",
    2,
    (
        DocumentPage(
            1,
            "Objective: assess adolescents using an AI chatbot in a cross-sectional "
            "research design. Participants: 120 adolescent students completed a survey.",
        ),
        DocumentPage(
            2,
            "Methods: a questionnaire included a validated wellbeing scale. "
            "Results showed a correlation, not causation. "
            "Limitations: self-report data may be affected by response bias.",
        ),
    ),
)


class FakeAnalyst:
    @property
    def model_id(self) -> str:
        return "fake-analyst"

    async def extract(self, snippets: tuple[LiteratureSnippet, ...]) -> tuple[ProposedFinding, ...]:
        first = next(snippet for snippet in snippets if snippet.locator == "PDF page 1")
        return (
            ProposedFinding(
                LiteratureFacet.AIM,
                first.snippet_id,
                "Objective: assess adolescents using an AI chatbot",
                "Assess adolescent use of an AI chatbot.",
            ),
        )


class BadQuoteAnalyst(FakeAnalyst):
    async def extract(self, snippets: tuple[LiteratureSnippet, ...]) -> tuple[ProposedFinding, ...]:
        return (
            ProposedFinding(
                LiteratureFacet.SAMPLE,
                snippets[0].snippet_id,
                "This text is invented by the model",
                "A fabricated sample size.",
            ),
        )


@pytest.mark.asyncio
async def test_extracts_page_grounded_facet_and_flags_missing() -> None:
    result = await ExtractLiteratureProfile(FakeAnalyst()).execute(DOC)
    assert result.page_count == 2
    assert len(result.findings) == len(FACET_ORDER)
    assert result.model == "fake-analyst"
    aim = result.findings[0]
    assert aim.facet is LiteratureFacet.AIM
    assert aim.status is FindingStatus.GROUNDED
    assert aim.locator == "PDF page 1"
    assert aim.quote is not None
    assert aim.quote in DOC.pages[0].text
    assert all(item.status is FindingStatus.NOT_IDENTIFIED for item in result.findings[1:])
    assert "not absent from the paper" in result.caveat


@pytest.mark.asyncio
async def test_hallucinated_quote_is_discarded_with_value() -> None:
    result = await ExtractLiteratureProfile(BadQuoteAnalyst()).execute(DOC)
    sample = next(item for item in result.findings if item.facet is LiteratureFacet.SAMPLE)
    assert sample.status is FindingStatus.REJECTED_QUOTE
    assert sample.quote is None and sample.value is None and sample.locator is None


@pytest.mark.asyncio
async def test_all_null_model_fields_are_not_identified() -> None:
    class NullAnalyst(FakeAnalyst):
        async def extract(self, snippets: SourceSnippets) -> tuple[ProposedFinding, ...]:
            return (ProposedFinding(LiteratureFacet.METHOD, None, None, None),)

    result = await ExtractLiteratureProfile(NullAnalyst()).execute(DOC)
    assert all(field.status is FindingStatus.NOT_IDENTIFIED for field in result.findings)


@pytest.mark.asyncio
async def test_duplicate_model_field_does_not_override_a_quote() -> None:
    class DuplicateAnalyst(FakeAnalyst):
        async def extract(self, snippets: SourceSnippets) -> tuple[ProposedFinding, ...]:
            x = await super().extract(snippets)
            return x + x

    result = await ExtractLiteratureProfile(DuplicateAnalyst()).execute(DOC)
    assert result.findings[0].status is FindingStatus.REJECTED_QUOTE
    assert result.findings[0].rejection_reason is LiteratureRejectionReason.DUPLICATE_FIELD


def test_snippet_selection_has_stable_source_loci_and_strict_limit() -> None:
    first = collect_snippets(DOC)
    assert first == collect_snippets(DOC)
    assert len(first) <= 12
    assert len({x.snippet_id for x in first}) == len(first)
    for snippet in first:
        number = int(snippet.locator.removeprefix("PDF page "))
        assert snippet.passage in DOC.pages[number - 1].text


@pytest.mark.asyncio
async def test_groq_adapter_parses_source_bounded_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer fake-key"
        body = json.loads(request.content)
        assert body["model"] == "openai/gpt-oss-20b"
        assert "snippet_id" in body["messages"][1]["content"]
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "fields": [
                                        {
                                            "field": "aim",
                                            "snippet_id": "p1-w1",
                                            "quote": "Objective: assess adolescents",
                                            "value": "Assess adolescents.",
                                        }
                                    ]
                                }
                            )
                        }
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        found = await GroqLiteratureAnalyst(client, "fake-key").extract(
            (LiteratureSnippet("p1-w1", "PDF page 1", "Objective: assess adolescents."),)
        )
    assert found[0].facet is LiteratureFacet.AIM
    assert found[0].quote == "Objective: assess adolescents"


@pytest.mark.asyncio
async def test_groq_missing_key_does_not_invoke_model() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(500))
    ) as client:
        with pytest.raises(EvidenceProviderUnavailable):
            await GroqLiteratureAnalyst(client, None).extract(
                (LiteratureSnippet("p1", "PDF page 1", "sample text"),)
            )


@pytest.mark.asyncio
async def test_invalid_provider_data_fails_without_fabricated_fallback() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, json={"choices": [{"message": {"content": '{"fields":"invalid"}'}}]}
        )
    )
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(EvidenceProviderFailure):
            await GroqLiteratureAnalyst(client, "fake-key").extract(
                (LiteratureSnippet("p1", "PDF page 1", "Some scientific text."),)
            )


class FakePdfExtractor:
    def extract(self, data: bytes, filename: str) -> ExtractedDocument:
        return DOC


@pytest.fixture
def api_client() -> Iterator[TestClient]:
    app = create_app(
        Settings(app_env="test", database_url="postgresql+asyncpg://u:p@localhost:5432/test")
    )
    app.dependency_overrides[get_pdf_extractor] = FakePdfExtractor
    app.dependency_overrides[get_literature_analyst] = FakeAnalyst
    client = TestClient(app)
    try:
        yield client
    finally:
        client.close()
        app.dependency_overrides.clear()


def test_literature_endpoint_requires_explicit_consent(api_client: TestClient) -> None:
    reply = api_client.post(
        "/api/v1/literature/analyze-pdf",
        files={"file": ("paper.pdf", b"%PDF-1.4", "application/pdf")},
        data={"share_excerpts_with_ai": "false"},
    )
    assert reply.status_code == 422
    assert "Explicit consent" in reply.json()["detail"]


def test_literature_endpoint_returns_source_grounded_fields(api_client: TestClient) -> None:
    reply = api_client.post(
        "/api/v1/literature/analyze-pdf",
        files={"file": ("paper.pdf", b"%PDF-1.4", "application/pdf")},
        data={"share_excerpts_with_ai": "true"},
    )
    assert reply.status_code == 200, reply.text
    data = reply.json()
    assert data["document_title"] == "Test paper.pdf"
    assert len(data["findings"]) == 6
    assert data["findings"][0]["status"] == "grounded"
    assert data["findings"][0]["locator"] == "PDF page 1"


@pytest.mark.asyncio
async def test_invalid_model_quote_has_explainable_reason() -> None:
    result = await ExtractLiteratureProfile(BadQuoteAnalyst()).execute(DOC)
    sample = next(item for item in result.findings if item.facet is LiteratureFacet.SAMPLE)
    assert sample.rejection_reason is LiteratureRejectionReason.QUOTE_NOT_FOUND
    assert sample.locator_repaired is False


@pytest.mark.asyncio
async def test_wrong_model_source_id_can_be_repaired_from_exact_pdf_quote() -> None:
    class WrongSource(FakeAnalyst):
        async def extract(self, snippets: SourceSnippets) -> tuple[ProposedFinding, ...]:
            assert any(x.locator == "PDF page 2" for x in snippets)
            return (
                ProposedFinding(
                    LiteratureFacet.LIMITATIONS,
                    "model-made-up-ID",
                    "Limitations: self-report data may be affected by response bias.",
                    "Self-report was a limitation.",
                ),
            )

    result = await ExtractLiteratureProfile(WrongSource()).execute(DOC)
    finding = next(
        item for item in result.findings if item.facet is LiteratureFacet.LIMITATIONS
    )
    assert finding.status is FindingStatus.GROUNDED
    assert finding.quote is not None
    assert finding.quote in DOC.pages[1].text
    assert finding.locator == "PDF page 2"
    assert finding.locator_repaired is True
    assert finding.rejection_reason is None


@pytest.mark.asyncio
async def test_quote_found_on_multiple_pages_without_valid_locator_is_rejected() -> None:
    repeated = "Limitations: participants were not randomly selected for this study."
    doc = ExtractedDocument(
        "Repeated.pdf",
        "sha-repeated",
        2,
        (DocumentPage(1, repeated), DocumentPage(2, repeated)),
    )

    class AmbiguousAnalyst(FakeAnalyst):
        async def extract(self, snippets: SourceSnippets) -> tuple[ProposedFinding, ...]:
            return (
                ProposedFinding(
                    LiteratureFacet.LIMITATIONS, "unknown", repeated, "Sampling limitation."
                ),
            )

    result = await ExtractLiteratureProfile(AmbiguousAnalyst()).execute(doc)
    field = result.findings[-1]
    assert field.status is FindingStatus.REJECTED_QUOTE
    assert field.rejection_reason is LiteratureRejectionReason.AMBIGUOUS_LOCATION
    assert field.value is None


@pytest.mark.asyncio
async def test_incomplete_or_overlong_quotes_are_not_preserved() -> None:
    class MissingValueAnalyst(FakeAnalyst):
        async def extract(self, snippets: SourceSnippets) -> tuple[ProposedFinding, ...]:
            return (
                ProposedFinding(
                    LiteratureFacet.METHOD, snippets[0].snippet_id, "cross-sectional", None
                ),
            )

    result = await ExtractLiteratureProfile(MissingValueAnalyst()).execute(DOC)
    field = result.findings[1]
    assert field.status is FindingStatus.REJECTED_QUOTE
    assert field.rejection_reason is LiteratureRejectionReason.INCOMPLETE_EVIDENCE
    assert field.quote is None


def test_literature_endpoint_requires_file(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/v1/literature/analyze-pdf",
        data={"share_excerpts_with_ai": "true"},
    )
    assert response.status_code == 422
