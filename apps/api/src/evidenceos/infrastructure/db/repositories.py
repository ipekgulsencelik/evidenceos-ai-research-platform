"""SQLAlchemy implementation of repository ports."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from evidenceos.domain.entities.project import ResearchDomain, ResearchProject
from evidenceos.infrastructure.db.models import ProjectRow


class SqlAlchemyProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, project: ResearchProject) -> None:
        self._session.add(
            ProjectRow(
                id=project.id,
                title=project.title,
                domain=project.domain.value,
                created_at=project.created_at,
            )
        )

    async def get(self, project_id: UUID) -> ResearchProject | None:
        row = await self._session.get(ProjectRow, project_id)
        if row is None:
            return None
        return ResearchProject(
            id=row.id,
            title=row.title,
            domain=ResearchDomain(row.domain),
            created_at=row.created_at,
        )
