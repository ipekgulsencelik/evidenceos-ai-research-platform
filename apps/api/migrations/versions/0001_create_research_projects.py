"""Create research projects.

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "research_projects",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("domain", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("domain IN ('academic', 'legal')", name="ck_research_projects_domain"),
    )
    op.create_index("ix_research_projects_created_at", "research_projects", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_research_projects_created_at", table_name="research_projects")
    op.drop_table("research_projects")
