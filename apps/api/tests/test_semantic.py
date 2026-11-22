"""Semantic analysis never trusts model-provided source IDs or calls without consent."""

import json
from collections.abc import Iterator
from dataclasses import replace
from typing import cast
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from evidenceos.application.use_cases.projects import CreateProject, CreateProjectCommand
from evidenceos.application.use_cases.semantic import CompareSemanticEvidence
from evidenceos.application.use_cases.workspace import SaveLiteratureAnalysis
from evidenceos.domain.entities.literature import (
    FindingStatus,
    LiteratureFacet,
    LiteratureFinding,
    LiteratureProfile,
)
from evidenceos.domain.entities.project import ResearchDomain, ResearchProject
from evidenceos.domain.entities.semantic import (
    ComparisonKind,
    ProposedSemanticComparison,
    SemanticDimension,
    SemanticExcerpt,
)
from evidenceos.domain.errors import InvalidResearchWorkspace, LiteratureEntryNotFound
from evidenceos.infrastructure.config import Settings
from evidenceos.infrastructure.providers.groq_evidence import (
    EvidenceProviderFailure,
    EvidenceProviderUnavailable,
)
from evidenceos.infrastructure.providers.groq_semantic import GroqSemanticGapAnalyst
from evidenceos.presentation.api.app import create_app
from evidenceos.presentation.api.dependencies import get_uow_factory
from evidenceos.presentation.api.routes.semantic import get_semantic_analyst
from tests.fakes import FakeLiteratureRepository, FakeUnitOfWork
from tests.test_workspace import example_profile


def profile(sha: str, *, has_sample: bool = True) -> LiteratureProfile:
    original = example_profile()
    findings = tuple(
        LiteratureFinding(
            item.facet,
            FindingStatus.GROUNDED,
            "Sample reported",
            "Sample: 180 students aged 15 to 18.",
            "PDF page 2",
        ) if has_sample and item.facet is LiteratureFacet.SAMPLE
        else LiteratureFinding(item.facet, FindingStatus.NOT_IDENTIFIED, None, None, None)
        for item in original.findings
    )
    return replace(original, sha256=sha * 64, findings=findings)


class FakeAnalyst:
    def __init__(self) -> None:
        self.calls = 0
        self.result: tuple[ProposedSemanticComparison, ...] = ()

    @property
    def model_id(self) -> str:
        return "test-semantic-model"

    async def compare(
        self, evidence: tuple[SemanticExcerpt, ...]
    ) -> tuple[ProposedSemanticComparison, ...]:
        self.calls += 1
        assert all(item.quote == "Sample: 180 students aged 15 to 18." for item in evidence)
        return self.result


async def seed() -> tuple[
    UUID, UUID, UUID, UUID, dict[UUID, ResearchProject], FakeLiteratureRepository
]:
    projects: dict[UUID, ResearchProject] = {}
    saved = FakeLiteratureRepository()

    def factory() -> FakeUnitOfWork:
        return FakeUnitOfWork(projects, saved)

    first = await CreateProject(factory).execute(
        CreateProjectCommand("First project", ResearchDomain.ACADEMIC)
    )
    second = await CreateProject(factory).execute(
        CreateProjectCommand("Second project", ResearchDomain.ACADEMIC)
    )
    a = await SaveLiteratureAnalysis(factory).execute(first.id, profile("a"))
    b = await SaveLiteratureAnalysis(factory).execute(first.id, profile("b"))
    await SaveLiteratureAnalysis(factory).execute(second.id, profile("c"))
    return first.id, second.id, a.id, b.id, projects, saved


@pytest.mark.asyncio
async def test_semantic_source_integrity_and_consent() -> None:
    project, _, a, b, projects, saved = await seed()
    analyst = FakeAnalyst()
    def factory() -> FakeUnitOfWork:
        return FakeUnitOfWork(projects, saved)

    compare = CompareSemanticEvidence(factory, analyst)
    with pytest.raises(InvalidResearchWorkspace, match="consent"):
        await compare.execute(project, (a, b), consent_to_share_quotes=False)
    assert analyst.calls == 0

    analyst.result = (
        ProposedSemanticComparison(
            SemanticDimension.POPULATION,
            ComparisonKind.POSSIBLE_ALIGNMENT,
            "Both selected excerpts describe adolescents.",
            "How do populations compare in the original studies?",
            ("s1:sample", "s2:sample"),
        ),
    )
    report = await compare.execute(project, (a, b), consent_to_share_quotes=True)
    assert analyst.calls == 1
    assert len(report.candidates) == 1
    assert report.candidates[0].references[0].entry_id == a
    assert report.candidates[0].references[1].entry_id == b
    assert report.candidates[0].references[0].locator == "PDF page 2"
    assert SemanticDimension.MEASUREMENT in report.insufficient_dimensions
    assert "NOT" in report.caveat


@pytest.mark.asyncio
async def test_model_made_up_citations_and_duplicates_are_discarded() -> None:
    project, _, a, b, projects, saved = await seed()
    analyst = FakeAnalyst()
    def factory() -> FakeUnitOfWork:
        return FakeUnitOfWork(projects, saved)

    analyst.result = (
        ProposedSemanticComparison(
            SemanticDimension.POPULATION,
            ComparisonKind.POSSIBLE_DIFFERENCE,
            "This is unsupported and cannot be cited.",
            "Could a different population be important?",
            ("s1:sample", "invented"),
        ),
        ProposedSemanticComparison(
            SemanticDimension.POPULATION,
            ComparisonKind.POSSIBLE_ALIGNMENT,
            "Same single document was cited twice.",
            "How should this be verified?",
            ("s1:sample", "s1:sample"),
        ),
        ProposedSemanticComparison(
            SemanticDimension.FINDINGS,
            ComparisonKind.POSSIBLE_ALIGNMENT,
            "Source IDs belong to population, not findings.",
            "What findings can be compared?",
            ("s1:sample", "s2:sample"),
        ),
    )
    result = await CompareSemanticEvidence(factory, analyst).execute(
        project, (a, b), consent_to_share_quotes=True
    )
    assert len(result.candidates) == 0
    assert result.skipped_candidates == 3


@pytest.mark.asyncio
async def test_missing_paired_evidence_never_calls_external_model() -> None:
    project, _, a, b, projects, saved = await seed()
    saved.entries[b] = replace(
        saved.entries[b],
        profile=profile("b", has_sample=False),
    )
    analyst = FakeAnalyst()
    def factory() -> FakeUnitOfWork:
        return FakeUnitOfWork(projects, saved)

    result = await CompareSemanticEvidence(factory, analyst).execute(
        project, (a, b), consent_to_share_quotes=True
    )
    assert analyst.calls == 0
    assert not result.candidates
    assert len(result.insufficient_dimensions) == 4


@pytest.mark.asyncio
async def test_cross_project_and_duplicate_document_blocked_before_model() -> None:
    project, other, a, b, projects, saved = await seed()
    analyst = FakeAnalyst()
    def factory() -> FakeUnitOfWork:
        return FakeUnitOfWork(projects, saved)

    with pytest.raises(LiteratureEntryNotFound):
        await CompareSemanticEvidence(factory, analyst).execute(
            other, (a, b), consent_to_share_quotes=True
        )
    with pytest.raises(InvalidResearchWorkspace):
        await CompareSemanticEvidence(factory, analyst).execute(
            project, (a, a), consent_to_share_quotes=True
        )
    saved.entries[b] = replace(saved.entries[b], profile=profile("a"))
    with pytest.raises(InvalidResearchWorkspace, match="different PDFs"):
        await CompareSemanticEvidence(factory, analyst).execute(
            project, (a, b), consent_to_share_quotes=True
        )
    assert analyst.calls == 0


@pytest.mark.asyncio
async def test_groq_adapter_uses_only_quotes_and_validated_json() -> None:
    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        requests.append(payload)
        return httpx.Response(
            200,
            json={
                "choices": [{
                    "message": {
                        "content": json.dumps({
                            "comparisons": [{
                                "dimension": "population",
                                "kind": "possible_difference",
                                "summary": "The quoted groups may differ in age.",
                                "research_question": "Are age groups comparable?",
                                "reference_ids": ["s1:sample", "s2:sample"],
                            }]
                        })
                    }
                }]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        analyst = GroqSemanticGapAnalyst(client, "test-key", "test-model")
        quotes = (
            SemanticExcerpt("s1:sample", uuid4(), "A", SemanticDimension.POPULATION,
                            "PDF page 1", "Adolescents aged 12 to 14"),
            SemanticExcerpt("s2:sample", uuid4(), "B", SemanticDimension.POPULATION,
                            "PDF page 2", "Adolescents aged 15 to 18"),
        )
        result = await analyst.compare(quotes)
        assert result[0].kind is ComparisonKind.POSSIBLE_DIFFERENCE
        assert len(requests) == 1
        messages = cast(list[dict[str, str]], requests[0]["messages"])
        sent = json.loads(messages[-1]["content"])
        assert sent["sources"][0]["quote"] == "Adolescents aged 12 to 14"
        assert "entry_id" not in sent["sources"][0]
        assert "page" in sent["sources"][0]

    async with httpx.AsyncClient() as client:
        with pytest.raises(EvidenceProviderUnavailable):
            await GroqSemanticGapAnalyst(client, None).compare(quotes)


@pytest.mark.asyncio
async def test_groq_adapter_rejects_invalid_output() -> None:
    async def bad_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "choices": [{"message": {"content": '{"comparisons":"invalid"}'}}]
        })

    async with httpx.AsyncClient(transport=httpx.MockTransport(bad_handler)) as client:
        analyst = GroqSemanticGapAnalyst(client, "test-key")
        with pytest.raises(EvidenceProviderFailure):
            await analyst.compare((
                SemanticExcerpt("s1:sample", uuid4(), "A", SemanticDimension.POPULATION,
                                "PDF page 1", "Population is described"),
            ))


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app(
        Settings(app_env="test", database_url="postgresql+asyncpg://u:p@localhost:5432/test")
    )
    projects: dict[UUID, ResearchProject] = {}
    literature = FakeLiteratureRepository()
    analyst = FakeAnalyst()
    analyst.result = (
        ProposedSemanticComparison(
            SemanticDimension.POPULATION,
            ComparisonKind.POSSIBLE_ALIGNMENT,
            "Both excerpts describe a student population.",
            "Are these participant groups comparable?",
            ("s1:sample", "s2:sample"),
        ),
    )
    app.dependency_overrides[get_uow_factory] = lambda: (
        lambda: FakeUnitOfWork(projects, literature)
    )
    app.dependency_overrides[get_semantic_analyst] = lambda: analyst
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_semantic_http_requires_consent_and_returns_real_source_quote(client: TestClient) -> None:
    project = client.post(
        "/api/v1/projects", json={"title": "Test project", "domain": "academic"}
    ).json()["id"]
    import anyio

    factory = cast(FastAPI, client.app).dependency_overrides[get_uow_factory]()

    async def create_entries() -> tuple[str, str]:
        first = await SaveLiteratureAnalysis(factory).execute(UUID(project), profile("a"))
        second = await SaveLiteratureAnalysis(factory).execute(UUID(project), profile("b"))
        return str(first.id), str(second.id)

    a, b = anyio.run(create_entries)
    endpoint = f"/api/v1/projects/{project}/semantic-gaps"
    denied = client.post(endpoint, json={
        "entry_ids": [a, b], "consent_to_share_quotes": False
    })
    assert denied.status_code == 422
    response = client.post(endpoint, json={
        "entry_ids": [a, b], "consent_to_share_quotes": True
    })
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["candidates"][0]["references"][0]["quote"] == (
        "Sample: 180 students aged 15 to 18."
    )
    assert result["candidates"][0]["references"][1]["entry_id"] == b
