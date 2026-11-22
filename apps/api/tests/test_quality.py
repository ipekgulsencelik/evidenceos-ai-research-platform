"""Reporting coverage is not risk of bias; human reviews are append-only and scoped."""

from collections.abc import Iterator
from dataclasses import replace
from typing import cast
from uuid import UUID, uuid4

import anyio
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from evidenceos.application.use_cases.projects import CreateProject, CreateProjectCommand
from evidenceos.application.use_cases.quality import (
    GetQualityChecklist,
    ListQualityReviewHistory,
    SaveQualityReview,
    SaveQualityReviewCommand,
)
from evidenceos.application.use_cases.workspace import SaveLiteratureAnalysis
from evidenceos.domain.entities.literature import (
    FindingStatus,
    LiteratureFacet,
    LiteratureFinding,
    LiteratureProfile,
)
from evidenceos.domain.entities.project import ResearchDomain, ResearchProject
from evidenceos.domain.entities.quality import (
    ConcernJudgment,
    QualityDimension,
    ReportingJudgment,
)
from evidenceos.domain.errors import InvalidResearchWorkspace, LiteratureEntryNotFound
from evidenceos.infrastructure.config import Settings
from evidenceos.infrastructure.db.models import Base
from evidenceos.infrastructure.db.uow import SqlAlchemyUnitOfWork
from evidenceos.presentation.api.app import create_app
from evidenceos.presentation.api.dependencies import get_uow_factory
from tests.fakes import FakeLiteratureRepository, FakeQualityRepository, FakeUnitOfWork
from tests.test_workspace import example_profile


def reported_profile() -> LiteratureProfile:
    base = example_profile()
    findings = tuple(
        LiteratureFinding(
            facet=facet,
            status=FindingStatus.GROUNDED,
            value="Source quotation is present, content requires human review.",
            quote="Survey data were collected at one time point.",
            locator="PDF page 2",
        )
        if facet in (LiteratureFacet.METHOD, LiteratureFacet.SAMPLE)
        else finding
        for finding in base.findings
        for facet in (finding.facet,)
    )
    return replace(base, findings=findings)


@pytest.mark.asyncio
async def test_coverage_not_conflated_with_reporting_and_latest_review() -> None:
    projects: dict[UUID, ResearchProject] = {}
    literature = FakeLiteratureRepository()
    quality = FakeQualityRepository()

    def make_uow() -> FakeUnitOfWork:
        return FakeUnitOfWork(projects, literature, quality=quality)

    project = await CreateProject(make_uow).execute(
        CreateProjectCommand("Adolescent evidence appraisal", ResearchDomain.ACADEMIC)
    )
    entry = await SaveLiteratureAnalysis(make_uow).execute(project.id, reported_profile())
    checklist = await GetQualityChecklist(make_uow).execute(project.id, entry.id)
    assert len(checklist.indicators) == 7
    sampling = next(
        row for row in checklist.indicators if row.dimension is QualityDimension.SAMPLING
    )
    assert sampling.coverage == "excerpt_available"
    assert sampling.source_excerpts[0].locator == "PDF page 2"
    psychometrics = next(
        row for row in checklist.indicators if row.dimension is QualityDimension.PSYCHOMETRICS
    )
    assert psychometrics.coverage == "not_assessable_from_excerpts"
    assert checklist.latest_reviews == ()
    assert "NOT a validated risk-of-bias" in checklist.caveat

    first = await SaveQualityReview(make_uow).execute(
        SaveQualityReviewCommand(
            project.id, entry.id, QualityDimension.SAMPLING,
            ReportingJudgment.NOT_ASSESSED, ConcernJudgment.NOT_ASSESSED,
            False, "Need full-text confirmation",
        )
    )
    second = await SaveQualityReview(make_uow).execute(
        SaveQualityReviewCommand(
            project.id, entry.id, QualityDimension.SAMPLING,
            ReportingJudgment.UNCLEAR_AFTER_REVIEW, ConcernJudgment.POTENTIAL_CONCERN,
            True, "Sampling process not clear on full-text review",
        )
    )
    assert first.id != second.id
    history = await ListQualityReviewHistory(make_uow).execute(project.id, entry.id)
    assert history == [second, first]
    refreshed = await GetQualityChecklist(make_uow).execute(project.id, entry.id)
    assert refreshed.latest_reviews == (second,)
    assert refreshed.indicators == checklist.indicators


@pytest.mark.asyncio
async def test_manual_judgments_require_original_pdf_check() -> None:
    projects: dict[UUID, ResearchProject] = {}
    records = FakeLiteratureRepository()

    def factory() -> FakeUnitOfWork:
        return FakeUnitOfWork(projects, records)

    project = await CreateProject(factory).execute(
        CreateProjectCommand("Study quality", ResearchDomain.ACADEMIC)
    )
    entry = await SaveLiteratureAnalysis(factory).execute(project.id, example_profile())
    with pytest.raises(InvalidResearchWorkspace, match="original PDF"):
        await SaveQualityReview(factory).execute(
            SaveQualityReviewCommand(
                project.id, entry.id, QualityDimension.DESIGN,
                ReportingJudgment.NOT_REPORTED_IN_FULL_TEXT,
                ConcernJudgment.NOT_ASSESSED,
                False,
                "This would be an unsupported paper-wide omission claim",
            )
        )
    with pytest.raises(InvalidResearchWorkspace, match="original PDF"):
        await SaveQualityReview(factory).execute(
            SaveQualityReviewCommand(
                project.id, entry.id, QualityDimension.PRECISION,
                ReportingJudgment.NOT_ASSESSED,
                ConcernJudgment.NO_CONCERN_IDENTIFIED,
                False, "",
            )
        )
    with pytest.raises(InvalidResearchWorkspace, match="1000"):
        await SaveQualityReview(factory).execute(
            SaveQualityReviewCommand(
                project.id, entry.id, QualityDimension.DESIGN,
                ReportingJudgment.NOT_ASSESSED,
                ConcernJudgment.NOT_ASSESSED,
                False, "x" * 1001,
            )
        )


@pytest.mark.asyncio
async def test_project_isolation_and_invalid_entries() -> None:
    projects: dict[UUID, ResearchProject] = {}
    records = FakeLiteratureRepository()
    quality = FakeQualityRepository()

    def factory() -> FakeUnitOfWork:
        return FakeUnitOfWork(projects, records, quality=quality)

    first = await CreateProject(factory).execute(
        CreateProjectCommand("First academic project", ResearchDomain.ACADEMIC)
    )
    second = await CreateProject(factory).execute(
        CreateProjectCommand("Second academic project", ResearchDomain.ACADEMIC)
    )
    entry = await SaveLiteratureAnalysis(factory).execute(first.id, example_profile())
    with pytest.raises(LiteratureEntryNotFound):
        await GetQualityChecklist(factory).execute(second.id, entry.id)
    with pytest.raises(LiteratureEntryNotFound):
        await SaveQualityReview(factory).execute(
            SaveQualityReviewCommand(
                second.id, entry.id, QualityDimension.DESIGN,
                ReportingJudgment.NOT_ASSESSED, ConcernJudgment.NOT_ASSESSED, False, "",
            )
        )
    with pytest.raises(LiteratureEntryNotFound):
        await ListQualityReviewHistory(factory).execute(second.id, entry.id)
    with pytest.raises(LiteratureEntryNotFound):
        await GetQualityChecklist(factory).execute(first.id, uuid4())
    assert quality.rows == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sqlite_quality_review_reloads_in_new_unit_of_work() -> None:
    pytest.importorskip("aiosqlite")
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)

        def factory() -> SqlAlchemyUnitOfWork:
            return SqlAlchemyUnitOfWork(sessions)

        project = await CreateProject(factory).execute(
            CreateProjectCommand("Quality review SQL", ResearchDomain.ACADEMIC)
        )
        entry = await SaveLiteratureAnalysis(factory).execute(project.id, reported_profile())
        created = await SaveQualityReview(factory).execute(
            SaveQualityReviewCommand(
                project.id, entry.id, QualityDimension.DESIGN,
                ReportingJudgment.REPORTED_IN_FULL_TEXT,
                ConcernJudgment.POTENTIAL_CONCERN, True, "Verify confounding",
            )
        )
        loaded = await GetQualityChecklist(factory).execute(project.id, entry.id)
        assert loaded.latest_reviews[0].id == created.id
        assert loaded.latest_reviews[0].note == "Verify confounding"
        assert len(await ListQualityReviewHistory(factory).execute(project.id, entry.id)) == 1
    finally:
        await engine.dispose()


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app(
        Settings(app_env="test", database_url="postgresql+asyncpg://u:p@localhost:5432/test")
    )
    projects: dict[UUID, ResearchProject] = {}
    records = FakeLiteratureRepository()
    quality = FakeQualityRepository()
    app.dependency_overrides[get_uow_factory] = lambda: lambda: FakeUnitOfWork(
        projects, records, quality=quality
    )
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_quality_api_reloads_history_and_rejects_cross_project(client: TestClient) -> None:
    project = client.post(
        "/api/v1/projects",
        json={"title": "Study quality", "domain": "academic"},
    ).json()["id"]
    factory = cast(FastAPI, client.app).dependency_overrides[get_uow_factory]()

    async def insert() -> str:
        entry = await SaveLiteratureAnalysis(factory).execute(UUID(project), reported_profile())
        return str(entry.id)

    entry_id = anyio.run(insert)
    base = f"/api/v1/projects/{project}/literature/{entry_id}"
    response = client.get(base + "/quality-checklist")
    assert response.status_code == 200, response.text
    assert len(response.json()["indicators"]) == 7
    invalid = client.post(
        base + "/quality-reviews",
        json={
            "dimension": "sampling",
            "reporting": "not_reported_in_full_text",
            "concern": "not_assessed",
            "checked_original": False,
            "note": "unsupported claim",
        },
    )
    assert invalid.status_code == 422
    saved = client.post(
        base + "/quality-reviews",
        json={
            "dimension": "sampling",
            "reporting": "unclear_after_review",
            "concern": "potential_concern",
            "checked_original": True,
            "note": "Need independent screening",
        },
    )
    assert saved.status_code == 201, saved.text
    assert len(client.get(base + "/quality-reviews").json()) == 1
    assert client.get(base + "/quality-checklist").json()["latest_reviews"][0]["note"] == (
        "Need independent screening"
    )
    second = client.post(
        "/api/v1/projects",
        json={"title": "Other research", "domain": "academic"},
    ).json()["id"]
    wrong = f"/api/v1/projects/{second}/literature/{entry_id}"
    assert client.get(wrong + "/quality-checklist").status_code == 404
    assert client.get(wrong + "/quality-reviews").status_code == 404
    assert client.post(
        wrong + "/quality-reviews",
        json={"dimension": "sampling", "checked_original": False},
    ).status_code == 404
