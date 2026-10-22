"""Store immutable EDL v2 revisions.

Revision ID: 0002_revisions
Revises: 0001_legacy
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_revisions"
down_revision = "0001_legacy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_revisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("edl", sa.JSON(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "revision", name="uq_project_revision"),
    )
    op.create_index("ix_project_revisions_project_id", "project_revisions", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_project_revisions_project_id", table_name="project_revisions")
    op.drop_table("project_revisions")

