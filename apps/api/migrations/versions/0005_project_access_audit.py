"""Create role-scoped project memberships and append-only access-decision audit events.

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_memberships",
        sa.Column("project_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("principal_key", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["research_projects.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "role IN ('owner', 'editor', 'reviewer', 'viewer')",
            name="ck_project_memberships_role",
        ),
        sa.PrimaryKeyConstraint("project_id", "principal_key"),
    )
    op.create_index(
        "ix_project_memberships_principal",
        "project_memberships",
        ["principal_key"],
    )
    op.create_table(
        "access_decision_events",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("actor_key", sa.String(length=64), nullable=False),
        # Deliberately not a FK: audit history survives future project deletion.
        sa.Column("project_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("outcome", sa.String(length=8), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "outcome IN ('allowed', 'denied')",
            name="ck_access_decision_outcome",
        ),
    )
    op.create_index(
        "ix_access_decisions_project_time",
        "access_decision_events",
        ["project_id", "created_at"],
    )
    op.create_index(
        "ix_access_decisions_actor_time",
        "access_decision_events",
        ["actor_key", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_access_decisions_actor_time", table_name="access_decision_events")
    op.drop_index("ix_access_decisions_project_time", table_name="access_decision_events")
    op.drop_table("access_decision_events")
    op.drop_index("ix_project_memberships_principal", table_name="project_memberships")
    op.drop_table("project_memberships")
