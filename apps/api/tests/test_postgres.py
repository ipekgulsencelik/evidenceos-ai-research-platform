"""Runs in GitHub Actions with a PostgreSQL service; skipped locally without a DSN."""

import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from evidenceos.application.use_cases.library import (
    ListLibraryItems,
    UpdateCatalogCommand,
    UpdateLibraryMetadata,
)
from evidenceos.application.use_cases.projects import (
    CreateProject,
    CreateProjectCommand,
    GetProject,
)
from evidenceos.application.use_cases.workspace import (
    GetLiteratureAnalysis,
    ListReviewRevisions,
    SaveLiteratureAnalysis,
    SaveReviewCommand,
    SaveReviewRevision,
)
from evidenceos.domain.entities.library import ReadingStatus
from evidenceos.domain.entities.literature import LiteratureFacet
from evidenceos.domain.entities.project import ResearchDomain
from evidenceos.infrastructure.db.uow import SqlAlchemyUnitOfWork
from tests.test_workspace import example_profile


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgres_write_read_in_real_database() -> None:
    dsn = os.getenv("EVIDENCEOS_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("requires an explicit disposable PostgreSQL test database")
    engine = create_async_engine(dsn)
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)

        def make_uow() -> SqlAlchemyUnitOfWork:
            return SqlAlchemyUnitOfWork(factory)

        async with engine.connect() as conn:
            assert (await conn.execute(text("SELECT 1"))).scalar_one() == 1
        item = await CreateProject(make_uow).execute(
            CreateProjectCommand("PostgreSQL real adapter", ResearchDomain.ACADEMIC)
        )
        loaded = await GetProject(make_uow).execute(item.id)
        assert loaded.id == item.id
        assert loaded.domain == ResearchDomain.ACADEMIC
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgres_literature_snapshots_and_audit_history() -> None:
    """GitHub Actions applies the real Alembic migration before this test."""
    dsn = os.getenv("EVIDENCEOS_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("requires an explicit disposable PostgreSQL test database")
    engine = create_async_engine(dsn)
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)

        def make_uow() -> SqlAlchemyUnitOfWork:
            return SqlAlchemyUnitOfWork(factory)

        project = await CreateProject(make_uow).execute(
            CreateProjectCommand("Postgres literature persistence", ResearchDomain.ACADEMIC)
        )
        entry = await SaveLiteratureAnalysis(make_uow).execute(project.id, example_profile())
        reloaded = await GetLiteratureAnalysis(make_uow).execute(project.id, entry.id)
        assert reloaded.profile.sha256 == entry.profile.sha256
        assert reloaded.profile.findings == entry.profile.findings

        revision = await SaveReviewRevision(make_uow).execute(
            SaveReviewCommand(
                project.id,
                entry.id,
                LiteratureFacet.LIMITATIONS,
                "Verify the sample",
                "Original PDF should be checked",
                True,
            )
        )
        historical = await ListReviewRevisions(make_uow).execute(project.id, entry.id)
        assert historical[0].id == revision.id
        assert historical[0].corrected_value == "Verify the sample"
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgres_catalog_metadata_survives_new_session() -> None:
    """Alembic revision 0003 must install the library metadata table."""
    dsn = os.getenv("EVIDENCEOS_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("requires an explicit disposable PostgreSQL database")
    engine = create_async_engine(dsn)
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)

        def make_uow() -> SqlAlchemyUnitOfWork:
            return SqlAlchemyUnitOfWork(factory)

        project = await CreateProject(make_uow).execute(
            CreateProjectCommand("Live catalog migration", ResearchDomain.ACADEMIC)
        )
        entry = await SaveLiteratureAnalysis(make_uow).execute(project.id, example_profile())
        await UpdateLibraryMetadata(make_uow).execute(
            UpdateCatalogCommand(
                project.id, entry.id, ReadingStatus.REVIEWED, ("Adolescents", "Methods")
            )
        )
        loaded = await ListLibraryItems(make_uow).execute(
            project.id, query="test paper", status=ReadingStatus.REVIEWED, tag="methods"
        )
        assert len(loaded) == 1
        assert loaded[0].metadata.tags == ("Adolescents", "Methods")
        assert loaded[0].entry.profile.findings == entry.profile.findings
    finally:
        await engine.dispose()
