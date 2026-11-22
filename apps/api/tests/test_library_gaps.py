"""Safe catalog and research-coverage behavior, tested without an external model."""

from collections.abc import Iterator
from dataclasses import replace
from typing import cast
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from evidenceos.application.use_cases.gaps import CompareEvidenceCoverage
from evidenceos.application.use_cases.library import (
    ListLibraryItems,
    UpdateCatalogCommand,
    UpdateLibraryMetadata,
    validate_tags,
)
from evidenceos.application.use_cases.projects import CreateProject, CreateProjectCommand
from evidenceos.application.use_cases.workspace import SaveLiteratureAnalysis
from evidenceos.domain.entities.library import ReadingStatus
from evidenceos.domain.entities.literature import (
    FACET_ORDER,
    FindingStatus,
    LiteratureFacet,
    LiteratureFinding,
    LiteratureProfile,
)
from evidenceos.domain.entities.project import ResearchDomain, ResearchProject
from evidenceos.domain.errors import InvalidResearchWorkspace, LiteratureEntryNotFound
from evidenceos.infrastructure.config import Settings
from evidenceos.infrastructure.db.models import Base
from evidenceos.infrastructure.db.uow import SqlAlchemyUnitOfWork
from evidenceos.presentation.api.app import create_app
from evidenceos.presentation.api.dependencies import get_uow_factory
from tests.fakes import FakeLibraryRepository, FakeLiteratureRepository, FakeUnitOfWork
from tests.test_workspace import example_profile


def make_profile(sha: str, title: str, *, supported: tuple[LiteratureFacet, ...]) -> LiteratureProfile:
    original = example_profile()
    findings = tuple(
        LiteratureFinding(
            facet=facet,
            status=(FindingStatus.GROUNDED if facet in supported else FindingStatus.NOT_IDENTIFIED),
            value="Explicitly described." if facet in supported else None,
            quote="An exact source excerpt." if facet in supported else None,
            locator="PDF page 1" if facet in supported else None,
        )
        for facet in FACET_ORDER
    )
    return replace(original, sha256=sha * 64, document_title=title, findings=findings)


@pytest.mark.asyncio
async def test_catalog_is_scoped_and_metadata_does_not_modify_evidence() -> None:
    projects: dict[UUID, ResearchProject] = {}
    literature = FakeLiteratureRepository()
    library = FakeLibraryRepository()

    def make_uow() -> FakeUnitOfWork:
        return FakeUnitOfWork(projects, literature, library)

    first = await CreateProject(make_uow).execute(
        CreateProjectCommand("Adolescent AI", ResearchDomain.ACADEMIC)
    )
    second = await CreateProject(make_uow).execute(
        CreateProjectCommand("Other project", ResearchDomain.ACADEMIC)
    )
    entry = await SaveLiteratureAnalysis(make_uow).execute(
        first.id,
        make_profile("a", "Adolescent chatbot study.pdf", supported=(LiteratureFacet.AIM,)),
    )
    stored = await UpdateLibraryMetadata(make_uow).execute(
        UpdateCatalogCommand(
            first.id, entry.id, ReadingStatus.READING, ("Adolescents", "Ethics", "ethics")
        )
    )
    assert stored.tags == ("Adolescents", "Ethics")
    items = await ListLibraryItems(make_uow).execute(
        first.id, query="CHATBOT", status=ReadingStatus.READING, tag="ethics"
    )
    assert len(items) == 1
    assert items[0].entry.profile == entry.profile
    assert items[0].metadata.status is ReadingStatus.READING
    assert await ListLibraryItems(make_uow).execute(second.id) == []
    with pytest.raises(LiteratureEntryNotFound):
        await UpdateLibraryMetadata(make_uow).execute(
            UpdateCatalogCommand(second.id, entry.id, ReadingStatus.REVIEWED, ())
        )
    assert (await ListLibraryItems(make_uow).execute(first.id))[0].metadata == stored


def test_tag_validation_rejects_unsafe_or_overlong_values() -> None:
    assert validate_tags((" Childhood ", "childhood", "AI")) == ("Childhood", "AI")
    with pytest.raises(InvalidResearchWorkspace):
        validate_tags(("<script>",))
    with pytest.raises(InvalidResearchWorkspace):
        validate_tags(tuple(str(i) for i in range(9)))
    with pytest.raises(InvalidResearchWorkspace):
        validate_tags((" " * 10,))


@pytest.mark.asyncio
async def test_gap_candidates_reference_grounded_quotes_only() -> None:
    projects: dict[UUID, ResearchProject] = {}
    literature = FakeLiteratureRepository()

    def make_uow() -> FakeUnitOfWork:
        return FakeUnitOfWork(projects, literature)

    project = await CreateProject(make_uow).execute(
        CreateProjectCommand("Research", ResearchDomain.ACADEMIC)
    )
    a = await SaveLiteratureAnalysis(make_uow).execute(
        project.id,
        make_profile("a", "Study A", supported=(LiteratureFacet.AIM, LiteratureFacet.SAMPLE)),
    )
    b = await SaveLiteratureAnalysis(make_uow).execute(
        project.id,
        make_profile("b", "Study B", supported=(LiteratureFacet.AIM,)),
    )
    result = await CompareEvidenceCoverage(make_uow).execute(project.id, (a.id, b.id))
    assert [x.facet for x in result.candidates] == [
        facet for facet in FACET_ORDER if facet is not LiteratureFacet.AIM
    ]
    sample = next(x for x in result.candidates if x.facet is LiteratureFacet.SAMPLE)
    assert sample.grounded_count == 1 and sample.total_count == 2
    assert sample.not_identified_entry_ids == (b.id,)
    assert len(sample.references) == 1
    assert sample.references[0].entry_id == a.id
    assert sample.references[0].locator == "PDF page 1"
    assert "NOT evidence" in result.caveat


@pytest.mark.asyncio
async def test_gap_scope_and_input_constraints() -> None:
    projects: dict[UUID, ResearchProject] = {}
    literature = FakeLiteratureRepository()

    def make_uow() -> FakeUnitOfWork:
        return FakeUnitOfWork(projects, literature)

    a = await CreateProject(make_uow).execute(
        CreateProjectCommand("Academic A", ResearchDomain.ACADEMIC)
    )
    b = await CreateProject(make_uow).execute(
        CreateProjectCommand("Academic B", ResearchDomain.ACADEMIC)
    )
    one = await SaveLiteratureAnalysis(make_uow).execute(a.id, make_profile("a", "A", supported=()))
    two = await SaveLiteratureAnalysis(make_uow).execute(b.id, make_profile("b", "B", supported=()))
    with pytest.raises(InvalidResearchWorkspace):
        await CompareEvidenceCoverage(make_uow).execute(a.id, (one.id, one.id))
    with pytest.raises(LiteratureEntryNotFound):
        await CompareEvidenceCoverage(make_uow).execute(a.id, (one.id, two.id))


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sqlite_library_metadata_persists_without_changing_snapshot() -> None:
    pytest.importorskip("aiosqlite")
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)

        def uow() -> SqlAlchemyUnitOfWork:
            return SqlAlchemyUnitOfWork(sessions)

        project = await CreateProject(uow).execute(
            CreateProjectCommand("Catalog database", ResearchDomain.ACADEMIC)
        )
        entry = await SaveLiteratureAnalysis(uow).execute(
            project.id, make_profile("c", "Real SQL record", supported=(LiteratureFacet.AIM,))
        )
        await UpdateLibraryMetadata(uow).execute(
            UpdateCatalogCommand(project.id, entry.id, ReadingStatus.REVIEWED, ("Methods",))
        )
        items = await ListLibraryItems(uow).execute(
            project.id, status=ReadingStatus.REVIEWED, tag="methods"
        )
        assert len(items) == 1
        assert items[0].metadata.tags == ("Methods",)
        assert items[0].entry.profile.findings == entry.profile.findings
    finally:
        await engine.dispose()


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app(
        Settings(app_env="test", database_url="postgresql+asyncpg://u:p@localhost:5432/test")
    )
    projects: dict[UUID, ResearchProject] = {}
    literature = FakeLiteratureRepository()
    catalog = FakeLibraryRepository()
    app.dependency_overrides[get_uow_factory] = lambda: (
        lambda: FakeUnitOfWork(projects, literature, catalog)
    )
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_http_library_and_gap_selection(client: TestClient) -> None:
    project = client.post(
        "/api/v1/projects", json={"title": "Project alpha", "domain": "academic"}
    ).json()["id"]
    project_id = UUID(project)
    store = cast(FastAPI, client.app).dependency_overrides[get_uow_factory]()
    assert callable(store)
    # For HTTP tests create snapshots via the shared fake repository.
    # The app dependency factory is a closure over the shared fake stores.
    import anyio

    async def seed() -> tuple[UUID, UUID]:
        first = await SaveLiteratureAnalysis(store).execute(
            project_id,
            make_profile("e", "Paper on chatbot emotions", supported=(LiteratureFacet.AIM,)),
        )
        second = await SaveLiteratureAnalysis(store).execute(
            project_id, make_profile("f", "Paper on sample", supported=(LiteratureFacet.SAMPLE,))
        )
        return first.id, second.id

    first, second = anyio.run(seed)
    base = f"/api/v1/projects/{project}/library"
    listing = client.get(base)
    assert listing.status_code == 200, listing.text
    assert len(listing.json()) == 2
    payload = {"status": "reviewed", "tags": ["AI", "Adolescents"]}
    updated = client.put(base + f"/{first}", json=payload)
    assert updated.status_code == 200, updated.text
    assert updated.json()["status"] == "reviewed"
    assert len(client.get(base, params={"status": "reviewed", "tag": "ai"}).json()) == 1
    assert client.put(base + f"/{first}", json={"status": "unknown", "tags": []}).status_code == 422
    gap = client.post(
        f"/api/v1/projects/{project}/research-gaps",
        json={"entry_ids": [str(first), str(second)]},
    )
    assert gap.status_code == 200, gap.text
    assert gap.json()["candidates"]
    assert (
        client.post(
            f"/api/v1/projects/{project}/research-gaps",
            json={"entry_ids": [str(first), str(first)]},
        ).status_code
        == 422
    )
