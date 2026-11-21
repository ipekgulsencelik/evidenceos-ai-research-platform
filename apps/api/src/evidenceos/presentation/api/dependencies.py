"""Composition boundary for infrastructure dependencies."""

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from evidenceos.domain.ports.repositories import UnitOfWorkFactory
from evidenceos.infrastructure.db.uow import SqlAlchemyUnitOfWork


def get_uow_factory(request: Request) -> UnitOfWorkFactory:
    session_factory = request.app.state.session_factory
    return lambda: SqlAlchemyUnitOfWork(session_factory)


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.session_factory() as session:
        yield session
