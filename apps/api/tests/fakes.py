"""In-memory implementations for fast use-case and HTTP tests."""

from types import TracebackType
from uuid import UUID

from evidenceos.domain.entities.project import ResearchProject
from evidenceos.domain.entities.workspace import LiteratureEntry, ReviewRevision
from evidenceos.domain.ports.workspace import LiteratureRepository
from evidenceos.domain.ports.repositories import ProjectRepository


class FakeProjectRepository:
    def __init__(self, store: dict[UUID, ResearchProject]) -> None:
        self._store = store
        self._pending: dict[UUID, ResearchProject] = {}

    async def add(self, project: ResearchProject) -> None:
        self._pending[project.id] = project

    async def get(self, project_id: UUID) -> ResearchProject | None:
        return self._store.get(project_id)

    async def list_recent(self, *, limit: int = 50) -> list[ResearchProject]:
        return sorted(self._store.values(), key=lambda row: row.created_at, reverse=True)[:limit]

    def flush(self) -> None:
        self._store.update(self._pending)
        self._pending.clear()


class FakeUnitOfWork:
    def __init__(self, store: dict[UUID, ResearchProject]) -> None:
        self._projects = FakeProjectRepository(store)
        self.committed = False
        self._literature = FakeLiteratureRepository()

    @property
    def projects(self) -> ProjectRepository:
        return self._projects

    @property
    def literature(self) -> LiteratureRepository:
        return self._literature

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


class FakeLiteratureRepository:
    def __init__(self) -> None:
        self.entries: dict[UUID, LiteratureEntry] = {}
        self.reviews: list[ReviewRevision] = []

    async def add(self, entry: LiteratureEntry) -> None:
        self.entries[entry.id] = entry

    async def get(self, entry_id: UUID) -> LiteratureEntry | None:
        return self.entries.get(entry_id)

    async def list_for_project(
        self, project_id: UUID, *, limit: int = 20
    ) -> list[LiteratureEntry]:
        return [row for row in self.entries.values() if row.project_id == project_id][:limit]

    async def add_review(self, revision: ReviewRevision) -> None:
        self.reviews.append(revision)

    async def list_reviews(
        self, entry_id: UUID, *, limit: int = 100
    ) -> list[ReviewRevision]:
        return [
            revision for revision in reversed(self.reviews)
            if revision.entry_id == entry_id
        ][:limit]
