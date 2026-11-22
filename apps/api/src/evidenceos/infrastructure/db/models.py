"""ORM mappings: never imported by domain or application layers."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ProjectRow(Base):
    __tablename__ = "research_projects"
    __table_args__ = (
        CheckConstraint("domain IN ('academic', 'legal')", name="ck_research_projects_domain"),
        Index("ix_research_projects_created_at", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    domain: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProjectMembershipRow(Base):
    __tablename__ = "project_memberships"
    __table_args__ = (
        CheckConstraint(
            "role IN ('owner', 'editor', 'reviewer', 'viewer')",
            name="ck_project_memberships_role",
        ),
        Index("ix_project_memberships_principal", "principal_key"),
    )

    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("research_projects.id", ondelete="CASCADE"),
        primary_key=True,
    )
    principal_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AccessDecisionRow(Base):
    __tablename__ = "access_decision_events"
    __table_args__ = (
        CheckConstraint(
            "outcome IN ('allowed', 'denied')",
            name="ck_access_decision_outcome",
        ),
        Index("ix_access_decisions_project_time", "project_id", "created_at"),
        Index("ix_access_decisions_actor_time", "actor_key", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    actor_key: Mapped[str] = mapped_column(String(64), nullable=False)
    project_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    outcome: Mapped[str] = mapped_column(String(8), nullable=False)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class LiteratureEntryRow(Base):
    __tablename__ = "literature_entries"
    __table_args__ = (Index("ix_literature_entries_project_created", "project_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("research_projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    page_count: Mapped[int] = mapped_column(nullable=False)
    text_page_count: Mapped[int] = mapped_column(nullable=False)
    model_id: Mapped[str] = mapped_column(String(128), nullable=False)
    findings: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    caveat: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ReviewRevisionRow(Base):
    __tablename__ = "literature_review_revisions"
    __table_args__ = (
        CheckConstraint(
            "facet IN ('aim', 'method', 'sample', 'instruments', 'findings', 'limitations')",
            name="ck_literature_review_facet",
        ),
        Index("ix_literature_revisions_entry_created", "entry_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    entry_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("literature_entries.id", ondelete="CASCADE"),
        nullable=False,
    )
    facet: Mapped[str] = mapped_column(String(32), nullable=False)
    corrected_value: Mapped[str] = mapped_column(String(500), nullable=False)
    note: Mapped[str] = mapped_column(String(1000), nullable=False)
    reviewed: Mapped[bool] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class LibraryMetadataRow(Base):
    __tablename__ = "literature_library_metadata"

    entry_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("literature_entries.id", ondelete="CASCADE"),
        primary_key=True,
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class QualityReviewRow(Base):
    __tablename__ = "quality_review_revisions"
    __table_args__ = (
        CheckConstraint(
            "reporting IN ('not_assessed', 'reported_in_full_text', 'unclear_after_review', "
            "'not_reported_in_full_text', 'not_applicable')",
            name="ck_quality_reporting",
        ),
        CheckConstraint(
            "concern IN ('not_assessed', 'potential_concern', 'no_concern_identified')",
            name="ck_quality_concern",
        ),
        Index("ix_quality_review_entry_dimension_created", "entry_id", "dimension", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    entry_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("literature_entries.id", ondelete="CASCADE"),
        nullable=False,
    )
    dimension: Mapped[str] = mapped_column(String(32), nullable=False)
    reporting: Mapped[str] = mapped_column(String(40), nullable=False)
    concern: Mapped[str] = mapped_column(String(32), nullable=False)
    checked_original: Mapped[bool] = mapped_column(nullable=False)
    note: Mapped[str] = mapped_column(String(1000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
