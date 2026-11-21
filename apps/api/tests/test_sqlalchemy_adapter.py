"""SQLite adapter integration test; production database is PostgreSQL."""

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from evidenceos.application.use_cases.projects import (
    CreateProject,
    CreateProjectCommand,
    GetProject,
)
from evidenceos.domain.entities.project import ResearchDomain
from evidenceos.domain.errors import ProjectNotFound
from evidenceos.infrastructure.db.models import Base
from evidenceos.infrastructure.db.uow import SqlAlchemyUnitOfWork


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sqlalchemy_uow_round_trip() -> None:
    pytest.importorskip("aiosqlite", reason="install uv dev dependencies for SQLite tests")
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        make_uow = lambda: SqlAlchemyUnitOfWork(session_factory)
        created = await CreateProject(make_uow).execute(
            CreateProjectCommand("Legal references", ResearchDomain.LEGAL)
        )
        found = await GetProject(make_uow).execute(created.id)
        assert found.id == created.id
        assert found.title == created.title
        assert found.domain == ResearchDomain.LEGAL
        assert found.created_at.replace(tzinfo=created.created_at.tzinfo) == created.created_at
        with pytest.raises(ProjectNotFound):
            await GetProject(make_uow).execute(uuid4())
    finally:
        await engine.dispose()
