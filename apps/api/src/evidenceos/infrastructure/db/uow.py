"""SQLAlchemy unit of work controls transaction lifetime."""

from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from evidenceos.domain.ports.access import AccessAuditRepository, MembershipRepository
from evidenceos.domain.ports.library import LibraryRepository
from evidenceos.domain.ports.quality import QualityReviewRepository
from evidenceos.domain.ports.repositories import ProjectRepository
from evidenceos.domain.ports.workspace import LiteratureRepository
from evidenceos.infrastructure.db.repositories import (
    SqlAlchemyAccessAuditRepository,
    SqlAlchemyLibraryRepository,
    SqlAlchemyLiteratureRepository,
    SqlAlchemyMembershipRepository,
    SqlAlchemyProjectRepository,
    SqlAlchemyQualityReviewRepository,
)


class SqlAlchemyUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._projects: SqlAlchemyProjectRepository
        self._literature: SqlAlchemyLiteratureRepository
        self._library: SqlAlchemyLibraryRepository
        self._quality: SqlAlchemyQualityReviewRepository
        self._memberships: SqlAlchemyMembershipRepository
        self._access_audit: SqlAlchemyAccessAuditRepository

    @property
    def projects(self) -> ProjectRepository:
        return self._projects

    @property
    def literature(self) -> LiteratureRepository:
        return self._literature

    @property
    def library(self) -> LibraryRepository:
        return self._library

    @property
    def quality(self) -> QualityReviewRepository:
        return self._quality

    @property
    def memberships(self) -> MembershipRepository:
        return self._memberships

    @property
    def access_audit(self) -> AccessAuditRepository:
        return self._access_audit

    async def __aenter__(self) -> "SqlAlchemyUnitOfWork":
        self._session = self._session_factory()
        self._projects = SqlAlchemyProjectRepository(self._session)
        self._literature = SqlAlchemyLiteratureRepository(self._session)
        self._library = SqlAlchemyLibraryRepository(self._session)
        self._quality = SqlAlchemyQualityReviewRepository(self._session)
        self._memberships = SqlAlchemyMembershipRepository(self._session)
        self._access_audit = SqlAlchemyAccessAuditRepository(self._session)
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
