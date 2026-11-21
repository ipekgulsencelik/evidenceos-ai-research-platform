"""Workspace persistence, project isolation and append-only review history."""

from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from evidenceos.application.use_cases.projects import CreateProject, CreateProjectCommand
from evidenceos.application.use_cases.workspace import (
    GetLiteratureAnalysis,
    ListLiteratureAnalyses,
    ListReviewRevisions,
    SaveLiteratureAnalysis,
    SaveReviewCommand,
    SaveReviewRevision,
)
from evidenceos.domain.entities.document import DocumentPage, ExtractedDocument
from evidenceos.domain.entities.literature import (
    FACET_ORDER,
    FindingStatus,
    LiteratureFacet,
    LiteratureFinding,
    LiteratureProfile,
    LiteratureSnippet,
    ProposedFinding,
)
from evidenceos.domain.entities.project import ResearchDomain, ResearchProject
from evidenceos.domain.errors import (
    InvalidResearchWorkspace,
    LiteratureEntryNotFound,
    ProjectNotFound,
)
from evidenceos.infrastructure.config import Settings
from evidenceos.infrastructure.db.models import Base
from evidenceos.infrastructure.db.uow import SqlAlchemyUnitOfWork
from evidenceos.presentation.api.app import create_app
from evidenceos.presentation.api.dependencies import get_uow_factory
from evidenceos.presentation.api.routes.literature import (
    get_literature_analyst,
    get_pdf_extractor,
)
from tests.fakes import FakeLiteratureRepository, FakeUnitOfWork


def example_profile() -> LiteratureProfile:
    return LiteratureProfile(
        document_title="Test paper.pdf",
        sha256="a" * 64,
        page_count=2,
        text_page_count=2,
        model="mock-model",
        findings=tuple(
            LiteratureFinding(
                facet=facet,
                status=(
                    FindingStatus.GROUNDED if facet is LiteratureFacet.AIM
                    else FindingStatus.NOT_IDENTIFIED
                ),
                value=("Evaluate chatbot use in adolescents." if facet is LiteratureFacet.AIM else None),
                quote=("Objective: evaluate chatbot use." if facet is LiteratureFacet.AIM else None),
                locator=("PDF page 1" if facet is LiteratureFacet.AIM else None),
            )
            for facet in FACET_ORDER
        ),
        caveat="Test-only synthetic literature extraction; human review required.",
    )


@pytest.mark.asyncio
async def test_project_scope_and_append_only_review_use_cases() -> None:
    projects: dict[UUID, ResearchProject] = {}
    literature = FakeLiteratureRepository()

    def make_uow() -> FakeUnitOfWork:
        return FakeUnitOfWork(projects, literature)

    project = await CreateProject(make_uow).execute(
        CreateProjectCommand("Test research", ResearchDomain.ACADEMIC)
    )
    second = await CreateProject(make_uow).execute(
        CreateProjectCommand("Other research", ResearchDomain.ACADEMIC)
    )
    legal = await CreateProject(make_uow).execute(
        CreateProjectCommand("Legal research", ResearchDomain.LEGAL)
    )
    entry = await SaveLiteratureAnalysis(make_uow).execute(project.id, example_profile())
    assert (await GetLiteratureAnalysis(make_uow).execute(project.id, entry.id)) == entry
    assert (await ListLiteratureAnalyses(make_uow).execute(project.id)) == [entry]
    assert await ListLiteratureAnalyses(make_uow).execute(second.id) == []

    with pytest.raises(LiteratureEntryNotFound):
        await GetLiteratureAnalysis(make_uow).execute(second.id, entry.id)
    with pytest.raises(InvalidResearchWorkspace):
        await SaveLiteratureAnalysis(make_uow).execute(legal.id, example_profile())
    with pytest.raises(ProjectNotFound):
        await SaveLiteratureAnalysis(make_uow).execute(uuid4(), example_profile())

    first = await SaveReviewRevision(make_uow).execute(
        SaveReviewCommand(project.id, entry.id, LiteratureFacet.AIM, "Initial", "Check paper", False)
    )
    second_note = await SaveReviewRevision(make_uow).execute(
        SaveReviewCommand(project.id, entry.id, LiteratureFacet.AIM, "Updated", "Checked", True)
    )
    history = await ListReviewRevisions(make_uow).execute(project.id, entry.id)
    assert len(history) == 2
    assert history[0] == second_note
    assert history[1] == first
    with pytest.raises(LiteratureEntryNotFound):
        await SaveReviewRevision(make_uow).execute(
            SaveReviewCommand(second.id, entry.id, LiteratureFacet.AIM, "", "", False)
        )
    with pytest.raises(InvalidResearchWorkspace):
        await SaveReviewRevision(make_uow).execute(
            SaveReviewCommand(project.id, entry.id, LiteratureFacet.AIM, "a" * 501, "", False)
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sqlite_literature_persists_across_unit_of_work_sessions() -> None:
    pytest.importorskip("aiosqlite")
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)

        def make_uow() -> SqlAlchemyUnitOfWork:
            return SqlAlchemyUnitOfWork(factory)

        project = await CreateProject(make_uow).execute(
            CreateProjectCommand("Database workspace", ResearchDomain.ACADEMIC)
        )
        entry = await SaveLiteratureAnalysis(make_uow).execute(project.id, example_profile())
        loaded = await GetLiteratureAnalysis(make_uow).execute(project.id, entry.id)
        assert loaded.profile.findings == entry.profile.findings
        assert loaded.profile.sha256 == entry.profile.sha256

        revision = await SaveReviewRevision(make_uow).execute(
            SaveReviewCommand(
                project.id, entry.id, LiteratureFacet.LIMITATIONS,
                "Researcher comment", "Review PDF page 2", True,
            )
        )
        assert revision.reviewed is True
        history = await ListReviewRevisions(make_uow).execute(project.id, entry.id)
        assert history[0].corrected_value == "Researcher comment"
        assert await ListLiteratureAnalyses(make_uow).execute(project.id) != []
    finally:
        await engine.dispose()


class FakePdfExtractor:
    def extract(self, data: bytes, filename: str) -> ExtractedDocument:
        return ExtractedDocument(
            title=filename,
            sha256="d" * 64,
            page_count=1,
            pages=(DocumentPage(1, "Objective: evaluate adolescent chatbot usage in a sample."),),
        )


class FakeAnalyst:
    @property
    def model_id(self) -> str:
        return "test-model"

    async def extract(
        self, snippets: tuple[LiteratureSnippet, ...]
    ) -> tuple[ProposedFinding, ...]:
        assert snippets
        return (
            ProposedFinding(
                LiteratureFacet.AIM,
                snippets[0].snippet_id,
                "Objective: evaluate adolescent chatbot usage",
                "Evaluate adolescent chatbot usage.",
            ),
        )


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app(
        Settings(app_env="test", database_url="postgresql+asyncpg://u:p@localhost:5432/test")
    )
    project_store: dict[UUID, ResearchProject] = {}
    literature_store = FakeLiteratureRepository()
    app.dependency_overrides[get_uow_factory] = (
        lambda: lambda: FakeUnitOfWork(project_store, literature_store)
    )
    app.dependency_overrides[get_pdf_extractor] = FakePdfExtractor
    app.dependency_overrides[get_literature_analyst] = FakeAnalyst
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_http_project_workspace_round_trip_and_review_history(client: TestClient) -> None:
    response = client.post(
        "/api/v1/projects",
        json={"title": "Adolescents and AI", "domain": "academic"},
    )
    assert response.status_code == 201, response.text
    project_id = response.json()["id"]
    listing = client.get("/api/v1/projects")
    assert listing.status_code == 200
    assert any(item["id"] == project_id for item in listing.json())

    url = f"/api/v1/projects/{project_id}/literature"
    analysis = client.post(
        url + "/analyze-pdf",
        files={"file": ("test-paper.pdf", b"%PDF-1.4", "application/pdf")},
        data={"share_excerpts_with_ai": "true"},
    )
    assert analysis.status_code == 201, analysis.text
    entry = analysis.json()
    assert entry["project_id"] == project_id
    assert entry["profile"]["sha256"] == "d" * 64
    assert entry["profile"]["findings"][0]["status"] == "grounded"
    saved_id = entry["id"]
    assert client.get(url).json()[0]["id"] == saved_id
    assert client.get(f"{url}/{saved_id}").json()["id"] == saved_id

    endpoint = f"{url}/{saved_id}/reviews"
    one = client.post(
        endpoint,
        json={"facet": "aim", "corrected_value": "First note", "reviewed": False},
    )
    two = client.post(
        endpoint,
        json={"facet": "aim", "corrected_value": "Second note", "reviewed": True},
    )
    assert one.status_code == two.status_code == 201
    revisions = client.get(endpoint).json()
    assert [revision["corrected_value"] for revision in revisions] == [
        "Second note", "First note"
    ]

    another = client.post(
        "/api/v1/projects", json={"title": "Another project", "domain": "academic"}
    ).json()["id"]
    assert client.get(f"/api/v1/projects/{another}/literature").json() == []
    assert client.get(f"/api/v1/projects/{another}/literature/{saved_id}").status_code == 404
    assert client.post(
        f"/api/v1/projects/{another}/literature/{saved_id}/reviews",
        json={"facet": "aim", "note": "cross-project"},
    ).status_code == 404


def test_http_validates_consent_and_review_payload(client: TestClient) -> None:
    project_id = client.post(
        "/api/v1/projects", json={"title": "Secure analysis", "domain": "academic"}
    ).json()["id"]
    base = f"/api/v1/projects/{project_id}/literature"
    denied = client.post(
        base + "/analyze-pdf",
        files={"file": ("study.pdf", b"%PDF-1.4", "application/pdf")},
        data={"share_excerpts_with_ai": "false"},
    )
    assert denied.status_code == 422
    assert "consent" in denied.text.lower()
    invalid = client.post(
        base + f"/{uuid4()}/reviews",
        json={"facet": "aim", "corrected_value": "x" * 501},
    )
    assert invalid.status_code == 422
