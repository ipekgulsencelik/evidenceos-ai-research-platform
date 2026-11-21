"""Mocked source-review tests; no live paid model calls."""

import json
from collections.abc import Iterator

import httpx
import pytest
from fastapi.testclient import TestClient

from evidenceos.application.use_cases.evidence import AssessEvidence, InvalidEvidenceInput
from evidenceos.domain.entities.evidence import (
    EvidenceJudgment,
    EvidenceSource,
    EvidenceVerdict,
)
from evidenceos.infrastructure.config import Settings
from evidenceos.infrastructure.providers.groq_evidence import (
    EvidenceProviderFailure,
    EvidenceProviderUnavailable,
    GroqEvidenceJudge,
)
from evidenceos.presentation.api.app import create_app
from evidenceos.presentation.api.routes.evidence import get_evidence_judge

SOURCE = EvidenceSource(
    "W1",
    "Study about adolescents",
    "The study found an association between sleep and well-being among adolescents.",
    "Results",
)


class FakeJudge:
    @property
    def model_id(self) -> str:
        return "test"

    async def judge(self, claim: str, source: EvidenceSource) -> EvidenceJudgment:
        return EvidenceJudgment(
            EvidenceVerdict.SUPPORTS,
            "an association between sleep and well-being",
            "This passage describes an association.",
        )


class BadQuoteJudge(FakeJudge):
    async def judge(self, claim: str, source: EvidenceSource) -> EvidenceJudgment:
        return EvidenceJudgment(
            EvidenceVerdict.SUPPORTS, "invented quotation", "Model-generated"
        )


@pytest.mark.asyncio
async def test_grounded_claim_retains_source_locator() -> None:
    report = await AssessEvidence(FakeJudge()).execute(
        "Sleep is associated with well-being", [SOURCE]
    )
    assert report.model == "test"
    assert report.rows[0].verdict is EvidenceVerdict.SUPPORTS
    assert report.rows[0].quote in SOURCE.passage
    assert report.rows[0].locator == "Results"


@pytest.mark.asyncio
async def test_fabricated_quote_is_downgraded() -> None:
    report = await AssessEvidence(BadQuoteJudge()).execute(
        "Sleep is associated with well-being", [SOURCE]
    )
    assert report.rows[0].verdict is EvidenceVerdict.INSUFFICIENT
    assert report.rows[0].quote is None


@pytest.mark.asyncio
async def test_duplicate_sources_are_rejected() -> None:
    with pytest.raises(InvalidEvidenceInput, match="unique"):
        await AssessEvidence(FakeJudge()).execute(
            "Sleep is associated with well-being", [SOURCE, SOURCE]
        )


@pytest.mark.asyncio
async def test_missing_provider_key_fails_closed() -> None:
    async with httpx.AsyncClient() as client:
        with pytest.raises(EvidenceProviderUnavailable):
            await GroqEvidenceJudge(client, None).judge("A research claim", SOURCE)


@pytest.mark.asyncio
async def test_provider_receives_passage_and_parses_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.groq.com"
        assert request.headers["Authorization"] == "Bearer test-key"
        sent = json.loads(request.content)
        assert SOURCE.passage in sent["messages"][1]["content"]
        assert sent["response_format"] == {"type": "json_object"}
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "verdict": "insufficient",
                                    "quote": None,
                                    "explanation": "Evidence does not prove causation.",
                                }
                            )
                        }
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await GroqEvidenceJudge(client, "test-key").judge(
            "Sleep causes well-being", SOURCE
        )
    assert result.verdict is EvidenceVerdict.INSUFFICIENT


@pytest.mark.asyncio
async def test_unexpected_model_payload_is_an_error() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={}))
    ) as client:
        with pytest.raises(EvidenceProviderFailure):
            await GroqEvidenceJudge(client, "test-key").judge("Research claim here", SOURCE)


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app(
        Settings(app_env="test", database_url="postgresql+asyncpg://u:p@localhost:5432/test")
    )
    app.dependency_overrides[get_evidence_judge] = FakeJudge
    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        test_client.close()
        app.dependency_overrides.clear()


def test_evidence_http_endpoint(client: TestClient) -> None:
    response = client.post(
        "/api/v1/evidence/assess",
        json={
            "claim": "Sleep is associated with well-being",
            "sources": [
                {
                    "source_id": SOURCE.source_id,
                    "title": SOURCE.title,
                    "passage": SOURCE.passage,
                    "locator": SOURCE.locator,
                }
            ],
        },
    )
    assert response.status_code == 200
    assert response.json()["rows"][0]["quote"] in SOURCE.passage
    assert "Human review" in response.json()["caveat"]


def test_invalid_payload_is_rejected(client: TestClient) -> None:
    result = client.post(
        "/api/v1/evidence/assess", json={"claim": "too short", "sources": []}
    )
    assert result.status_code == 422
