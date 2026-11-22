"""Research library state is separate from immutable analysis evidence."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID


class ReadingStatus(StrEnum):
    TO_READ = "to_read"
    READING = "reading"
    REVIEWED = "reviewed"


@dataclass(frozen=True, slots=True)
class LibraryMetadata:
    entry_id: UUID
    status: ReadingStatus
    tags: tuple[str, ...]
    updated_at: datetime

    @classmethod
    def create(
        cls, entry_id: UUID, status: ReadingStatus, tags: tuple[str, ...]
    ) -> "LibraryMetadata":
        return cls(entry_id, status, tags, datetime.now(UTC))
