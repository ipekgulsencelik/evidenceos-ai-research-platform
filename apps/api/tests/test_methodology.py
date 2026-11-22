"""Methodology triage keeps project isolation, consent and source evidence boundaries."""

import json
from collections.abc import Iterator
from dataclasses import replace
from typing import cast
from uuid import UUID, uuid4

import anyio
import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from evidenceos.application.use_cases.methodology import ReviewStudyMethodology
from evidenceos.application.use_cases.projects import CreateProject, CreateProjectCommand
from evidenceos.application.use_cases.workspace import SaveLiteratureAnalysis
from evidenceos.domain.entities.literature import (
    FindingStatus,
    LiteratureFacet,
    LiteratureFinding,
    LiteratureProfile,
)
from evidenceos.domain.entities.methodology import (
    MethodologyAspect,
    MethodologySource,
    MethodologyStatus,
    ProposedMethodologyObservation,
)
from evidenceos.domain.entities.project import ResearchDomain, ResearchProject
from evidenceos.domain.errors import InvalidResearchWorkspace, LiteratureEntryNotFound
from evidenceos.infrastructure.config import Settings
from evidenceos.infrastructure.providers.groq_evidence import (
    EvidenceProviderFailure,
    EvidenceProviderUnavailable,
)
from evidenceos.infrastructure.providers.groq_methodology import GroqMethodologyAnalyst
from evidenceos.presentation.api.app import create_app
from evidenceos.presentation.api.dependencies import get_uow_factory
from evidenceos.presentation.api.routes.methodology import get_methodology_analyst
from tests.fakes import FakeLiteratureRepository, FakeUnitOfWork
from tests.test_workspace import example_profile


def study(sha: str, with_sources: bool = True) -> LiteratureProfile:
    base = example_profile()
    values = {
        LiteratureFacet.METHOD: "The survey used a cross-sectional design.",
        LiteratureFacet.SAMPLE: "A convenience sample of 120 students was enrolled.",
        LiteratureFacet.INSTRUMENTS: "A researcher-created motivation checklist was used.",
        LiteratureFacet.FINDINGS: "The reported correlation was r = -0.28.",
        LiteratureFacet.LIMITATIONS: "Self-report bias may affect interpretation.",
    }
    findings = tuple(
        LiteratureFinding(
            facet=facet,
            status=FindingStatus.GROUNDED if with_sources else FindingStatus.NOT_IDENTIFIED,
            value=quote if with_sources else None,
            quote=quote if with_sources else None,
            locator="PDF page 2" if with_sources else None,
        )
        for facet, quote in values.items()
    )
    return replace(base, sha256=sha * 64, document_title="Methodology test.pdf", findings=findings)


class FakeAnalyst:
    def __init__(self) -> None:
        self.calls = 0
        self.result: tuple[ProposedMethodologyObservation, ...] = ()
        self.received: tuple[MethodologySource, ...] = ()

    @property
    def model_id(self) -> str:
        return "methodology-fake"

    async def assess(
        self, sources: tuple[MethodologySource, ...]
    ) -> tuple[ProposedMethodologyObservation, ...]:
        self.calls += 1
        self.received = sources
        return self.result


async def seed() -> tuple[
    UUID, UUID, UUID, dict[UUID, ResearchProject], FakeLiteratureRepository
]:
    projects: dict[UUID, ResearchProject] = {}
    records = FakeLiteratureRepository()

    def factory() -> FakeUnitOfWork:
        return FakeUnitOfWork(projects, records)

    first = await CreateProject(factory).execute(
        CreateProjectCommand("Methodology project", ResearchDomain.ACADEMIC)
    )
    other = await CreateProject(factory).execute(
        CreateProjectCommand("Different project", ResearchDomain.ACADEMIC)
    )
    entry = await SaveLiteratureAnalysis(factory).execute(first.id, study("a"))
    return first.id, other.id, entry.id, projects, records


@pytest.mark.asyncio
async def test_methodology_consent_and_original_source_quotations() -> None:
    project, _, entry, projects, records = await seed()
    analyst = FakeAnalyst()

    def factory() -> FakeUnitOfWork:
        return FakeUnitOfWork(projects, records)

    reviewer = ReviewStudyMethodology(factory, analyst)
    with pytest.raises(InvalidResearchWorkspace, match="consent"):
        await reviewer.execute(project, entry, consent_to_share_quotes=False)
    assert analyst.calls == 0

    analyst.result = (
        ProposedMethodologyObservation(
            MethodologyAspect.DESIGN,
            MethodologyStatus.NEEDS_REVIEW,
            "The excerpt describes a cross-sectional survey design.",
            "Is the reporting sufficient to rule out causal inference?",
            ("f:method",),
        ),
        ProposedMethodologyObservation(
            MethodologyAspect.INSTRUMENTS,
            MethodologyStatus.REPORTED_IN_EXCERPT,
            "The excerpt names a researcher-created motivation checklist.",
            "What items and constructs were measured?",
            ("f:instruments",),
        ),
    )
    report = await reviewer.execute(project, entry, consent_to_share_quotes=True)
    assert analyst.calls == 1
    assert len(analyst.received) == 5
    assert len(report.observations) == 7
    design = report.observations[0]
    assert design.sources[0].quote == "The survey used a cross-sectional design."
    assert design.sources[0].locator == "PDF page 2"
    assert report.observations[3].status is MethodologyStatus.NOT_ASSESSABLE
    assert report.observations[3].sources == ()
    assert "NOT" in report.caveat or "not a risk-of-bias" in report.caveat


@pytest.mark.asyncio
async def test_methodology_rejects_unknown_wrong_facet_and_duplicate_sources() -> None:
    project, _, entry, projects, records = await seed()
    analyst = FakeAnalyst()

    def factory() -> FakeUnitOfWork:
        return FakeUnitOfWork(projects, records)

    analyst.result = (
        ProposedMethodologyObservation(
            MethodologyAspect.DESIGN,
            MethodologyStatus.REPORTED_IN_EXCERPT,
            "An invented source cannot support this claim.",
            "How can this be substantiated?",
            ("invented",),
        ),
        ProposedMethodologyObservation(
            MethodologyAspect.SAMPLING,
            MethodologyStatus.REPORTED_IN_EXCERPT,
            "An instrument quotation cannot support sampling.",
            "Is sampling reported?",
            ("f:instruments",),
        ),
        ProposedMethodologyObservation(
            MethodologyAspect.PSYCHOMETRICS,
            MethodologyStatus.REPORTED_IN_EXCERPT,
            "Duplicate references are invalid.",
            "Are there actual reliability metrics?",
            ("f:instruments", "f:instruments"),
        ),
        ProposedMethodologyObservation(
            MethodologyAspect.DESIGN,
            MethodologyStatus.NOT_ASSESSABLE,
            "No source quotation provided for this.",
            "What does the method actually report?",
            (),
        ),
    )
    report = await ReviewStudyMethodology(factory, analyst).execute(
        project, entry, consent_to_share_quotes=True
    )
    assert report.discarded_model_observations == 4
    assert all(row.status is MethodologyStatus.NOT_ASSESSABLE for row in report.observations)
    assert all(row.sources == () for row in report.observations)


@pytest.mark.asyncio
async def test_no_excerpts_means_no_model_call_and_no_invented_methodology() -> None:
    project, _, entry, projects, records = await seed()
    records.entries[entry] = replace(records.entries[entry], profile=study("a", False))
    analyst = FakeAnalyst()

    def factory() -> FakeUnitOfWork:
        return FakeUnitOfWork(projects, records)

    report = await ReviewStudyMethodology(factory, analyst).execute(
        project, entry, consent_to_share_quotes=True
    )
    assert analyst.calls == 0
    assert len(report.observations) == 7
    assert all(item.status is MethodologyStatus.NOT_ASSESSABLE for item in report.observations)


@pytest.mark.asyncio
async def test_cross_project_and_missing_record_do_not_call_model() -> None:
    project, other, entry, projects, records = await seed()
    analyst = FakeAnalyst()

    def factory() -> FakeUnitOfWork:
        return FakeUnitOfWork(projects, records)

    with pytest.raises(LiteratureEntryNotFound):
        await ReviewStudyMethodology(factory, analyst).execute(
            other, entry, consent_to_share_quotes=True
        )
    with pytest.raises(LiteratureEntryNotFound):
        await ReviewStudyMethodology(factory, analyst).execute(
            project, uuid4(), consent_to_share_quotes=True
        )
    assert analyst.calls == 0


@pytest.mark.asyncio
async def test_groq_adapter_sends_only_selected_quotations() -> None:
    captured: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        value = json.loads(request.content)
        captured.append(value)
        content = json.dumps({
            "observations": [{
                "aspect": "sampling",
                "status": "needs_review",
                "observation": "A convenience sample is reported.",
                "review_question": "How representative are these participants?",
                "reference_ids": ["f:sample"],
            }]
        })
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    quotes = (
        MethodologySource(
            "f:sample", LiteratureFacet.SAMPLE, "PDF page 2",
            "A convenience sample of 120 students was enrolled.",
        ),
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await GroqMethodologyAnalyst(client, "test-key", "mock").assess(quotes)
    assert result[0].aspect is MethodologyAspect.SAMPLING
    messages = cast(list[dict[str, str]], captured[0]["messages"])
    sent = json.loads(messages[-1]["content"])
    assert sent["evidence"][0]["quote"] == quotes[0].quote
    assert "document_title" not in sent["evidence"][0]
    assert "entry_id" not in sent["evidence"][0]

    async with httpx.AsyncClient() as client:
        with pytest.raises(EvidenceProviderUnavailable):
            await GroqMethodologyAnalyst(client, None).assess(quotes)


@pytest.mark.asyncio
async def test_groq_adapter_rejects_bad_json() -> None:
    async def broken(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"choices": [{"message": {"content": '{"observations":"wrong"}'}}]}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(broken)) as client:
        with pytest.raises(EvidenceProviderFailure):
            await GroqMethodologyAnalyst(client, "test-key").assess(
                (MethodologySource("f:method", LiteratureFacet.METHOD, "PDF page 1", "A study"),)
            )


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app(
        Settings(app_env="test", database_url="postgresql+asyncpg://u:p@localhost:5432/test")
    )
    projects: dict[UUID, ResearchProject] = {}
    saved = FakeLiteratureRepository()
    analyst = FakeAnalyst()
    analyst.result = (
        ProposedMethodologyObservation(
            MethodologyAspect.DESIGN,
            MethodologyStatus.NEEDS_REVIEW,
            "The authors describe a cross-sectional design.",
            "Does the paper address residual confounding?",
            ("f:method",),
        ),
    )
    app.dependency_overrides[get_uow_factory] = lambda: lambda: FakeUnitOfWork(projects, saved)
    app.dependency_overrides[get_methodology_analyst] = lambda: analyst
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_methodology_api_consent_scope_and_source_response(client: TestClient) -> None:
    project = client.post(
        "/api/v1/projects", json={"title": "Methodology study", "domain": "academic"}
    ).json()["id"]
    factory = cast(FastAPI, client.app).dependency_overrides[get_uow_factory]()

    async def save() -> str:
        entry = await SaveLiteratureAnalysis(factory).execute(UUID(project), study("a"))
        return str(entry.id)

    entry_id = anyio.run(save)
    path = f"/api/v1/projects/{project}/literature/{entry_id}/methodology-review"
    denied = client.post(path, json={"consent_to_share_quotes": False})
    assert denied.status_code == 422
    result = client.post(path, json={"consent_to_share_quotes": True})
    assert result.status_code == 200, result.text
    output = result.json()
    assert len(output["observations"]) == 7
    assert output["entry_id"] == entry_id
    assert output["observations"][0]["sources"][0]["quote"] == (
        "The survey used a cross-sectional design."
    )
    second = client.post(
        "/api/v1/projects", json={"title": "Other project", "domain": "academic"}
    ).json()["id"]
    assert client.post(
        f"/api/v1/projects/{second}/literature/{entry_id}/methodology-review",
        json={"consent_to_share_quotes": True},
    ).status_code == 404
