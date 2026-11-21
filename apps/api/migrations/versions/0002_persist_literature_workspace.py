"""Persist project-scoped literature snapshots and reviewer history.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "literature_entries",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("text_page_count", sa.Integer(), nullable=False),
        sa.Column("model_id", sa.String(length=128), nullable=False),
        sa.Column("findings", sa.JSON(), nullable=False),
        sa.Column("caveat", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["research_projects.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "ix_literature_entries_project_created",
        "literature_entries",
        ["project_id", "created_at"],
    )
    op.create_table(
        "literature_review_revisions",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("entry_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("facet", sa.String(length=32), nullable=False),
        sa.Column("corrected_value", sa.String(length=500), nullable=False),
        sa.Column("note", sa.String(length=1000), nullable=False),
        sa.Column("reviewed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "facet IN ('aim', 'method', 'sample', 'instruments', 'findings', 'limitations')",
            name="ck_literature_review_facet",
        ),
        sa.ForeignKeyConstraint(
            ["entry_id"], ["literature_entries.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "ix_literature_revisions_entry_created",
        "literature_review_revisions",
        ["entry_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_literature_revisions_entry_created",
        table_name="literature_review_revisions",
    )
    op.drop_table("literature_review_revisions")
    op.drop_index("ix_literature_entries_project_created", table_name="literature_entries")
    op.drop_table("literature_entries")
