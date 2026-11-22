"""SQLAlchemy implementation of repository ports."""

from dataclasses import asdict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from evidenceos.domain.entities.library import LibraryMetadata, ReadingStatus
from evidenceos.domain.entities.literature import (
    FindingStatus,
    LiteratureFacet,
    LiteratureFinding,
    LiteratureProfile,
    LiteratureRejectionReason,
)
from evidenceos.domain.entities.project import ResearchDomain, ResearchProject
from evidenceos.domain.entities.workspace import LiteratureEntry, ReviewRevision
from evidenceos.infrastructure.db.models import (
    LiteratureEntryRow,
    LibraryMetadataRow,
    ProjectRow,
    ReviewRevisionRow,
)


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

    async def list_recent(self, *, limit: int = 50) -> list[ResearchProject]:
        result = await self._session.scalars(
            select(ProjectRow)
            .order_by(ProjectRow.created_at.desc(), ProjectRow.id.desc())
            .limit(limit)
        )
        return [
            ResearchProject(
                id=row.id,
                title=row.title,
                domain=ResearchDomain(row.domain),
                created_at=row.created_at,
            )
            for row in result.all()
        ]

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


class SqlAlchemyLiteratureRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, entry: LiteratureEntry) -> None:
        self._session.add(
            LiteratureEntryRow(
                id=entry.id,
                project_id=entry.project_id,
                title=entry.profile.document_title,
                sha256=entry.profile.sha256,
                page_count=entry.profile.page_count,
                text_page_count=entry.profile.text_page_count,
                model_id=entry.profile.model,
                findings=[asdict(field) for field in entry.profile.findings],
                caveat=entry.profile.caveat,
                created_at=entry.created_at,
            )
        )

    @staticmethod
    def _to_entity(row: LiteratureEntryRow) -> LiteratureEntry:
        findings: list[LiteratureFinding] = []
        for raw in row.findings:
            findings.append(
                LiteratureFinding(
                    facet=LiteratureFacet(str(raw["facet"])),
                    status=FindingStatus(str(raw["status"])),
                    value=raw["value"] if isinstance(raw["value"], str) else None,
                    quote=raw["quote"] if isinstance(raw["quote"], str) else None,
                    locator=raw["locator"] if isinstance(raw["locator"], str) else None,
                    rejection_reason=(
                        LiteratureRejectionReason(str(raw["rejection_reason"]))
                        if raw.get("rejection_reason")
                        else None
                    ),
                    locator_repaired=raw.get("locator_repaired") is True,
                )
            )
        return LiteratureEntry(
            id=row.id,
            project_id=row.project_id,
            profile=LiteratureProfile(
                document_title=row.title,
                sha256=row.sha256,
                page_count=row.page_count,
                text_page_count=row.text_page_count,
                model=row.model_id,
                findings=tuple(findings),
                caveat=row.caveat,
            ),
            created_at=row.created_at,
        )

    async def get(self, entry_id: UUID) -> LiteratureEntry | None:
        row = await self._session.get(LiteratureEntryRow, entry_id)
        return self._to_entity(row) if row is not None else None

    async def list_for_project(self, project_id: UUID, *, limit: int = 20) -> list[LiteratureEntry]:
        result = await self._session.scalars(
            select(LiteratureEntryRow)
            .where(LiteratureEntryRow.project_id == project_id)
            .order_by(LiteratureEntryRow.created_at.desc(), LiteratureEntryRow.id.desc())
            .limit(limit)
        )
        return [self._to_entity(row) for row in result.all()]

    async def add_review(self, revision: ReviewRevision) -> None:
        self._session.add(
            ReviewRevisionRow(
                id=revision.id,
                entry_id=revision.entry_id,
                facet=revision.facet.value,
                corrected_value=revision.corrected_value,
                note=revision.note,
                reviewed=revision.reviewed,
                created_at=revision.created_at,
            )
        )

    async def list_reviews(self, entry_id: UUID, *, limit: int = 100) -> list[ReviewRevision]:
        result = await self._session.scalars(
            select(ReviewRevisionRow)
            .where(ReviewRevisionRow.entry_id == entry_id)
            .order_by(ReviewRevisionRow.created_at.desc(), ReviewRevisionRow.id.desc())
            .limit(limit)
        )
        return [
            ReviewRevision(
                id=row.id,
                entry_id=row.entry_id,
                facet=LiteratureFacet(row.facet),
                corrected_value=row.corrected_value,
                note=row.note,
                reviewed=row.reviewed,
                created_at=row.created_at,
            )
            for row in result.all()
        ]



class SqlAlchemyLibraryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, entry_id: UUID) -> LibraryMetadata | None:
        row = await self._session.get(LibraryMetadataRow, entry_id)
        if row is None:
            return None
        return LibraryMetadata(
            row.entry_id, ReadingStatus(row.status), tuple(row.tags), row.updated_at
        )

    async def upsert(self, metadata: LibraryMetadata) -> None:
        row = await self._session.get(LibraryMetadataRow, metadata.entry_id)
        if row is None:
            self._session.add(
                LibraryMetadataRow(
                    entry_id=metadata.entry_id,
                    status=metadata.status.value,
                    tags=list(metadata.tags),
                    updated_at=metadata.updated_at,
                )
            )
        else:
            row.status = metadata.status.value
            row.tags = list(metadata.tags)
            row.updated_at = metadata.updated_at
