"""Runs in GitHub Actions with a PostgreSQL service; skipped locally without a DSN."""

import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from evidenceos.application.use_cases.access import AssignProjectRole, EnforceProjectAccess
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
from evidenceos.application.use_cases.quality import (
    GetQualityChecklist,
    ListQualityReviewHistory,
    SaveQualityReview,
    SaveQualityReviewCommand,
)
from evidenceos.application.use_cases.workspace import (
    GetLiteratureAnalysis,
    ListReviewRevisions,
    SaveLiteratureAnalysis,
    SaveReviewCommand,
    SaveReviewRevision,
)
from evidenceos.domain.entities.access import (
    Principal,
    ProjectAction,
    ProjectRole,
    stable_subject_key,
)
from evidenceos.domain.entities.library import ReadingStatus
from evidenceos.domain.entities.literature import LiteratureFacet
from evidenceos.domain.entities.project import ResearchDomain
from evidenceos.domain.entities.quality import (
    ConcernJudgment,
    QualityDimension,
    ReportingJudgment,
)
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


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgres_quality_revision_migration_and_latest_judgments() -> None:
    """Real migration 0004 must preserve the human quality-review history."""
    dsn = os.getenv("EVIDENCEOS_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("requires an explicit disposable PostgreSQL test database")
    engine = create_async_engine(dsn)
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)

        def make_uow() -> SqlAlchemyUnitOfWork:
            return SqlAlchemyUnitOfWork(factory)

        project = await CreateProject(make_uow).execute(
            CreateProjectCommand("Human quality review", ResearchDomain.ACADEMIC)
        )
        entry = await SaveLiteratureAnalysis(make_uow).execute(project.id, example_profile())
        first = await SaveQualityReview(make_uow).execute(
            SaveQualityReviewCommand(
                project.id,
                entry.id,
                QualityDimension.DESIGN,
                ReportingJudgment.NOT_ASSESSED,
                ConcernJudgment.NOT_ASSESSED,
                False,
                "Before full-text review",
            )
        )
        second = await SaveQualityReview(make_uow).execute(
            SaveQualityReviewCommand(
                project.id,
                entry.id,
                QualityDimension.DESIGN,
                ReportingJudgment.UNCLEAR_AFTER_REVIEW,
                ConcernJudgment.POTENTIAL_CONCERN,
                True,
                "Need verification",
            )
        )
        checklist = await GetQualityChecklist(make_uow).execute(project.id, entry.id)
        assert len(checklist.indicators) == 7
        assert checklist.latest_reviews[0].id == second.id
        assert checklist.latest_reviews[0].reporting is ReportingJudgment.UNCLEAR_AFTER_REVIEW
        revisions = await ListQualityReviewHistory(make_uow).execute(project.id, entry.id)
        assert revisions == [second, first]
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgres_project_membership_rbac_and_access_history() -> None:
    """Alembic 0005 preserves scoped memberships and append-only access decisions."""
    dsn = os.getenv("EVIDENCEOS_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("requires an explicit disposable PostgreSQL test database")
    engine = create_async_engine(dsn)
    try:
        sessions = async_sessionmaker(engine, expire_on_commit=False)

        def factory() -> SqlAlchemyUnitOfWork:
            return SqlAlchemyUnitOfWork(sessions)

        alice = Principal(stable_subject_key("https://issuer.example", "alice"), "oidc_user")
        bob = Principal(stable_subject_key("https://issuer.example", "bob"), "oidc_user")
        project = await CreateProject(factory).execute(
            CreateProjectCommand("Rbac audit migration", ResearchDomain.ACADEMIC),
            actor=alice,
        )
        async with factory() as uow:
            assert await uow.memberships.role_for(project.id, alice.key) is ProjectRole.OWNER
            assert await uow.memberships.role_for(project.id, bob.key) is None
            assert [p.id for p in await uow.projects.list_for_principal(alice.key)] == [project.id]
            assert await uow.projects.list_for_principal(bob.key) == []

        await AssignProjectRole(factory).execute(
            alice, project.id, bob.key, ProjectRole.VIEWER, "test-request"
        )
        await EnforceProjectAccess(factory).execute(bob, project.id, ProjectAction.READ)
        from evidenceos.domain.errors import ProjectNotFound

        with pytest.raises(ProjectNotFound):
            await EnforceProjectAccess(factory).execute(
                bob, project.id, ProjectAction.WRITE, "denied-request"
            )
        async with factory() as uow:
            history = await uow.access_audit.latest(project.id)
            assert any(e.action == "project.create" and e.outcome == "allowed" for e in history)
            assert any(e.action == "membership.assign" for e in history)
            denied = [e for e in history if e.outcome == "denied"]
            assert len(denied) == 1
            assert denied[0].actor_key == bob.key
            assert denied[0].request_id == "denied-request"
    finally:
        await engine.dispose()
