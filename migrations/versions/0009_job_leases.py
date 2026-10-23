"""Add nullable lease metadata without rewriting existing local jobs.

Revision ID: 0009_job_leases
Revises: 0008_narrative_3d
"""

import sqlalchemy as sa
from alembic import op

revision = "0009_job_leases"
down_revision = "0008_narrative_3d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("lease_owner", sa.String(120), nullable=True))
    op.add_column("jobs", sa.Column("lease_expires_at", sa.DateTime(timezone=True),
                                    nullable=True))
    op.add_column("jobs", sa.Column("heartbeat_at", sa.DateTime(timezone=True),
                                    nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "heartbeat_at")
    op.drop_column("jobs", "lease_expires_at")
    op.drop_column("jobs", "lease_owner")
