"""ORM mappings: never imported by domain or application layers."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, JSON, String, Text, Uuid
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


class LiteratureEntryRow(Base):
    __tablename__ = "literature_entries"
    __table_args__ = (
        Index("ix_literature_entries_project_created", "project_id", "created_at"),
    )

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
