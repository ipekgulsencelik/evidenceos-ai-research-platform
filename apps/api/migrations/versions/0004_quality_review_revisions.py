"""Add append-only human quality and reporting triage revisions.

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "quality_review_revisions",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("entry_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("dimension", sa.String(length=32), nullable=False),
        sa.Column("reporting", sa.String(length=40), nullable=False),
        sa.Column("concern", sa.String(length=32), nullable=False),
        sa.Column("checked_original", sa.Boolean(), nullable=False),
        sa.Column("note", sa.String(length=1000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["entry_id"], ["literature_entries.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "dimension IN ('design', 'sampling', 'measurement', 'psychometrics', "
            "'analysis', 'precision', 'limitations')",
            name="ck_quality_dimension",
        ),
        sa.CheckConstraint(
            "reporting IN ('not_assessed', 'reported_in_full_text', "
            "'unclear_after_review', 'not_reported_in_full_text', 'not_applicable')",
            name="ck_quality_reporting",
        ),
        sa.CheckConstraint(
            "concern IN ('not_assessed', 'potential_concern', 'no_concern_identified')",
            name="ck_quality_concern",
        ),
        sa.CheckConstraint(
            "checked_original OR (reporting = 'not_assessed' AND concern = 'not_assessed')",
            name="ck_quality_original_review",
        ),
    )
    op.create_index(
        "ix_quality_review_entry_dimension_created",
        "quality_review_revisions",
        ["entry_id", "dimension", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_quality_review_entry_dimension_created",
        table_name="quality_review_revisions",
    )
    op.drop_table("quality_review_revisions")
