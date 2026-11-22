"""Add study metadata for the local research library.

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "literature_library_metadata",
        sa.Column("entry_id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('to_read', 'reading', 'reviewed')",
            name="ck_literature_library_status",
        ),
        sa.ForeignKeyConstraint(["entry_id"], ["literature_entries.id"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table("literature_library_metadata")
