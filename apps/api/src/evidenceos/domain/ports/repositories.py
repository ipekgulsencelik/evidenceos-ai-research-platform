"""Persistence abstractions owned by the domain."""

from collections.abc import Callable
from types import TracebackType
from typing import Protocol
from uuid import UUID

from evidenceos.domain.entities.project import ResearchProject


class ProjectRepository(Protocol):
    async def add(self, project: ResearchProject) -> None: ...

    async def get(self, project_id: UUID) -> ResearchProject | None: ...


class UnitOfWork(Protocol):
    @property
    def projects(self) -> ProjectRepository: ...

    async def __aenter__(self) -> "UnitOfWork": ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...


UnitOfWorkFactory = Callable[[], UnitOfWork]
