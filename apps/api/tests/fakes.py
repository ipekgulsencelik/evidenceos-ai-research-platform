"""In-memory implementations for fast use-case and HTTP tests."""

from types import TracebackType
from uuid import UUID

from evidenceos.domain.entities.project import ResearchProject
from evidenceos.domain.ports.repositories import ProjectRepository


class FakeProjectRepository:
    def __init__(self, store: dict[UUID, ResearchProject]) -> None:
        self._store = store
        self._pending: dict[UUID, ResearchProject] = {}

    async def add(self, project: ResearchProject) -> None:
        self._pending[project.id] = project

    async def get(self, project_id: UUID) -> ResearchProject | None:
        return self._store.get(project_id)

    def flush(self) -> None:
        self._store.update(self._pending)
        self._pending.clear()


class FakeUnitOfWork:
    def __init__(self, store: dict[UUID, ResearchProject]) -> None:
        self._projects = FakeProjectRepository(store)
        self.committed = False

    @property
    def projects(self) -> ProjectRepository:
        return self._projects

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    async def commit(self) -> None:
        self._projects.flush()
        self.committed = True
