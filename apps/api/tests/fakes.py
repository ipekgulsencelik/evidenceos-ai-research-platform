"""In-memory implementations for fast use-case and HTTP tests."""

from types import TracebackType
from uuid import UUID

from evidenceos.domain.entities.access import (
    AccessDecisionEvent,
    ProjectMembership,
    ProjectRole,
)
from evidenceos.domain.entities.library import LibraryMetadata
from evidenceos.domain.entities.project import ResearchProject
from evidenceos.domain.entities.quality import QualityDimension, QualityReviewRevision
from evidenceos.domain.entities.workspace import LiteratureEntry, ReviewRevision
from evidenceos.domain.ports.access import AccessAuditRepository, MembershipRepository
from evidenceos.domain.ports.library import LibraryRepository
from evidenceos.domain.ports.quality import QualityReviewRepository
from evidenceos.domain.ports.repositories import ProjectRepository
from evidenceos.domain.ports.workspace import LiteratureRepository


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

    async def list_for_principal(
        self, principal_key: str, *, limit: int = 50
    ) -> list[ResearchProject]:
        # A replacement is injected by FakeUnitOfWork during enter in policy tests.
        return sorted(self._store.values(), key=lambda row: row.created_at, reverse=True)[:limit]

    def flush(self) -> None:
        self._store.update(self._pending)
        self._pending.clear()


class FakeLiteratureRepository:
    def __init__(self) -> None:
        self.entries: dict[UUID, LiteratureEntry] = {}
        self.reviews: list[ReviewRevision] = []

    async def add(self, entry: LiteratureEntry) -> None:
        self.entries[entry.id] = entry

    async def get(self, entry_id: UUID) -> LiteratureEntry | None:
        return self.entries.get(entry_id)

    async def list_for_project(self, project_id: UUID, *, limit: int = 20) -> list[LiteratureEntry]:
        return [row for row in self.entries.values() if row.project_id == project_id][:limit]

    async def add_review(self, revision: ReviewRevision) -> None:
        self.reviews.append(revision)

    async def list_reviews(self, entry_id: UUID, *, limit: int = 100) -> list[ReviewRevision]:
        return [revision for revision in reversed(self.reviews) if revision.entry_id == entry_id][
            :limit
        ]


class FakeLibraryRepository:
    def __init__(self) -> None:
        self.data: dict[UUID, LibraryMetadata] = {}

    async def get(self, entry_id: UUID) -> LibraryMetadata | None:
        return self.data.get(entry_id)

    async def upsert(self, metadata: LibraryMetadata) -> None:
        self.data[metadata.entry_id] = metadata


class FakeQualityRepository:
    def __init__(self) -> None:
        self.rows: list[QualityReviewRevision] = []

    async def add(self, revision: QualityReviewRevision) -> None:
        self.rows.append(revision)

    async def latest(
        self, entry_id: UUID, dimension: QualityDimension
    ) -> QualityReviewRevision | None:
        return next(
            (
                row
                for row in reversed(self.rows)
                if row.entry_id == entry_id and row.dimension is dimension
            ),
            None,
        )

    async def history(self, entry_id: UUID, *, limit: int = 100) -> list[QualityReviewRevision]:
        return [row for row in reversed(self.rows) if row.entry_id == entry_id][:limit]


class FakeMembershipRepository:
    def __init__(
        self, rows: dict[tuple[UUID, str], ProjectRole] | None = None
    ) -> None:
        self.rows = rows if rows is not None else {}

    async def role_for(self, project_id: UUID, principal_key: str) -> ProjectRole | None:
        return self.rows.get((project_id, principal_key))

    async def upsert(self, membership: ProjectMembership) -> None:
        self.rows[(membership.project_id, membership.principal_key)] = membership.role

    async def project_ids_for(
        self, principal_key: str, *, limit: int = 50
    ) -> list[UUID]:
        return [
            project_id for (project_id, key), _ in self.rows.items()
            if key == principal_key
        ][:limit]


class FakeAccessAuditRepository:
    def __init__(self, events: list[AccessDecisionEvent] | None = None) -> None:
        self.events = events if events is not None else []

    async def append(self, event: AccessDecisionEvent) -> None:
        self.events.append(event)

    async def latest(self, project_id: UUID, *, limit: int = 100) -> list[AccessDecisionEvent]:
        return [event for event in reversed(self.events) if event.project_id == project_id][:limit]


class FakeUnitOfWork:
    def __init__(
        self,
        store: dict[UUID, ResearchProject],
        literature: FakeLiteratureRepository | None = None,
        library: FakeLibraryRepository | None = None,
        quality: FakeQualityRepository | None = None,
        memberships: FakeMembershipRepository | None = None,
        access_audit: FakeAccessAuditRepository | None = None,
    ) -> None:
        self._projects = FakeProjectRepository(store)
        self.committed = False
        self._literature = literature if literature is not None else FakeLiteratureRepository()
        self._library = library if library is not None else FakeLibraryRepository()
        self._quality = quality if quality is not None else FakeQualityRepository()
        self._memberships = memberships if memberships is not None else FakeMembershipRepository()
        self._access_audit = access_audit if access_audit is not None else FakeAccessAuditRepository()

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
