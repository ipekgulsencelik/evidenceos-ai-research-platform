"""SQLAlchemy implementation of repository ports."""

from dataclasses import asdict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from evidenceos.domain.entities.access import (
    AccessDecisionEvent,
    ProjectMembership,
    ProjectRole,
)
from evidenceos.domain.entities.library import LibraryMetadata, ReadingStatus
from evidenceos.domain.entities.literature import (
    FindingStatus,
    LiteratureFacet,
    LiteratureFinding,
    LiteratureProfile,
    LiteratureRejectionReason,
)
from evidenceos.domain.entities.project import ResearchDomain, ResearchProject
from evidenceos.domain.entities.quality import (
    ConcernJudgment,
    QualityDimension,
    QualityReviewRevision,
    ReportingJudgment,
)
from evidenceos.domain.entities.workspace import LiteratureEntry, ReviewRevision
from evidenceos.infrastructure.db.models import (
    AccessDecisionRow,
    LibraryMetadataRow,
    LiteratureEntryRow,
    ProjectMembershipRow,
    ProjectRow,
    QualityReviewRow,
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

    async def list_for_principal(
        self, principal_key: str, *, limit: int = 50
    ) -> list[ResearchProject]:
        result = await self._session.scalars(
            select(ProjectRow)
            .join(ProjectMembershipRow, ProjectMembershipRow.project_id == ProjectRow.id)
            .where(ProjectMembershipRow.principal_key == principal_key)
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


class SqlAlchemyMembershipRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def role_for(self, project_id: UUID, principal_key: str) -> ProjectRole | None:
        row = await self._session.get(ProjectMembershipRow, (project_id, principal_key))
        return ProjectRole(row.role) if row is not None else None

    async def upsert(self, membership: ProjectMembership) -> None:
        row = await self._session.get(
            ProjectMembershipRow, (membership.project_id, membership.principal_key)
        )
        if row is None:
            self._session.add(
                ProjectMembershipRow(
                    project_id=membership.project_id,
                    principal_key=membership.principal_key,
                    role=membership.role.value,
                    created_at=membership.created_at,
                )
            )
        else:
            row.role = membership.role.value

    async def list_for_project(
        self, project_id: UUID, *, limit: int = 100
    ) -> list[ProjectMembership]:
        result = await self._session.scalars(
            select(ProjectMembershipRow)
            .where(ProjectMembershipRow.project_id == project_id)
            .order_by(
                ProjectMembershipRow.created_at.asc(),
                ProjectMembershipRow.principal_key.asc(),
            )
            .limit(limit)
        )
        return [
            ProjectMembership(
                row.project_id, row.principal_key, ProjectRole(row.role), row.created_at
            )
            for row in result.all()
        ]

    async def delete(self, project_id: UUID, principal_key: str) -> bool:
        row = await self._session.get(ProjectMembershipRow, (project_id, principal_key))
        if row is None:
            return False
        await self._session.delete(row)
        return True

    async def project_ids_for(self, principal_key: str, *, limit: int = 50) -> list[UUID]:
        result = await self._session.scalars(
            select(ProjectMembershipRow.project_id)
            .where(ProjectMembershipRow.principal_key == principal_key)
            .order_by(ProjectMembershipRow.created_at.desc())
            .limit(limit)
        )
        return list(result.all())


class SqlAlchemyAccessAuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(self, event: AccessDecisionEvent) -> None:
        self._session.add(
            AccessDecisionRow(
                id=event.id,
                actor_key=event.actor_key,
                project_id=event.project_id,
                action=event.action,
                outcome=event.outcome,
                request_id=event.request_id,
                created_at=event.created_at,
            )
        )

    async def latest(self, project_id: UUID, *, limit: int = 100) -> list[AccessDecisionEvent]:
        result = await self._session.scalars(
            select(AccessDecisionRow)
            .where(AccessDecisionRow.project_id == project_id)
            .order_by(AccessDecisionRow.created_at.desc(), AccessDecisionRow.id.desc())
            .limit(limit)
        )
        return [
            AccessDecisionEvent(
                row.id,
                row.actor_key,
                row.project_id,
                row.action,
                row.outcome,
                row.request_id,
                row.created_at,
            )
            for row in result.all()
        ]


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


class SqlAlchemyQualityReviewRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_entity(row: QualityReviewRow) -> QualityReviewRevision:
        return QualityReviewRevision(
            row.id,
            row.entry_id,
            QualityDimension(row.dimension),
            ReportingJudgment(row.reporting),
            ConcernJudgment(row.concern),
            row.checked_original,
            row.note,
            row.created_at,
        )

    async def add(self, revision: QualityReviewRevision) -> None:
        self._session.add(
            QualityReviewRow(
                id=revision.id,
                entry_id=revision.entry_id,
                dimension=revision.dimension.value,
                reporting=revision.reporting.value,
                concern=revision.concern.value,
                checked_original=revision.checked_original,
                note=revision.note,
                created_at=revision.created_at,
            )
        )

    async def latest(
        self, entry_id: UUID, dimension: QualityDimension
    ) -> QualityReviewRevision | None:
        result = await self._session.scalars(
            select(QualityReviewRow)
            .where(
                QualityReviewRow.entry_id == entry_id,
                QualityReviewRow.dimension == dimension.value,
            )
            .order_by(QualityReviewRow.created_at.desc(), QualityReviewRow.id.desc())
            .limit(1)
        )
        row = result.first()
        return self._to_entity(row) if row is not None else None

    async def history(self, entry_id: UUID, *, limit: int = 100) -> list[QualityReviewRevision]:
        result = await self._session.scalars(
            select(QualityReviewRow)
            .where(QualityReviewRow.entry_id == entry_id)
            .order_by(QualityReviewRow.created_at.desc(), QualityReviewRow.id.desc())
            .limit(limit)
        )
        return [self._to_entity(row) for row in result.all()]
