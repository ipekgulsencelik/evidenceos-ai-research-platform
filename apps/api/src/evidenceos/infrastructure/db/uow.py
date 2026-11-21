"""SQLAlchemy unit of work controls transaction lifetime."""

from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from evidenceos.domain.ports.repositories import ProjectRepository
from evidenceos.infrastructure.db.repositories import SqlAlchemyProjectRepository


class SqlAlchemyUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._projects: SqlAlchemyProjectRepository

    @property
    def projects(self) -> ProjectRepository:
        return self._projects

    async def __aenter__(self) -> "SqlAlchemyUnitOfWork":
        self._session = self._session_factory()
        self._projects = SqlAlchemyProjectRepository(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._session is not None:
            try:
                await self._session.rollback()
            finally:
                await self._session.close()
                self._session = None

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("unit of work must be entered before committing")
        await self._session.commit()
