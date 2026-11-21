"""Framework-independent research project aggregate root."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from evidenceos.domain.errors import InvalidProjectTitle


class ResearchDomain(StrEnum):
    ACADEMIC = "academic"
    LEGAL = "legal"


@dataclass(frozen=True, slots=True)
class ResearchProject:
    id: UUID
    title: str
    domain: ResearchDomain
    created_at: datetime

    @classmethod
    def create(
        cls,
        title: str,
        domain: ResearchDomain,
        *,
        project_id: UUID | None = None,
        now: datetime | None = None,
    ) -> "ResearchProject":
        normalized = title.strip()
        if not 3 <= len(normalized) <= 160:
            raise InvalidProjectTitle("title must contain between 3 and 160 characters")
        return cls(
            id=project_id or uuid4(),
            title=normalized,
            domain=domain,
            created_at=now or datetime.now(UTC),
        )
