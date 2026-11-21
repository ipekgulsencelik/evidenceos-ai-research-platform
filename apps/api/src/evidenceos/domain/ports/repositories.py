"""Persistence abstractions owned by the domain."""

from collections.abc import Callable
from types import TracebackType
from typing import Protocol
from uuid import UUID

from evidenceos.domain.entities.project import ResearchProject
from evidenceos.domain.ports.workspace import LiteratureRepository


class ProjectRepository(Protocol):
    async def add(self, project: ResearchProject) -> None: ...

    async def get(self, project_id: UUID) -> ResearchProject | None: ...

    async def list_recent(self, *, limit: int = 50) -> list[ResearchProject]: ...


class UnitOfWork(Protocol):
    @property
    def projects(self) -> ProjectRepository: ...

    @property
    def literature(self) -> LiteratureRepository: ...

    async def __aenter__(self) -> "UnitOfWork": ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...


UnitOfWorkFactory = Callable[[], UnitOfWork]
