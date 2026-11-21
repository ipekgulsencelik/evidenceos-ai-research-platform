"""Runs in GitHub Actions with a PostgreSQL service; skipped locally without a DSN."""

import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from evidenceos.application.use_cases.projects import (
    CreateProject,
    CreateProjectCommand,
    GetProject,
)
from evidenceos.domain.entities.project import ResearchDomain
from evidenceos.infrastructure.db.uow import SqlAlchemyUnitOfWork


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
