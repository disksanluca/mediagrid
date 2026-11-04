"""Cooperative cancellation signal for local creative AI.

Revision ID: 0014_creative_ai_cancellation
Revises: 0013_motion_artifact_review
"""

import sqlalchemy as sa
from alembic import op

revision = "0014_creative_ai_cancellation"
down_revision = "0013_motion_artifact_review"
branch_labels = None
depends_on = None


def upgrade():
    columns = {item["name"] for item in sa.inspect(op.get_bind()).get_columns("jobs")}
    if "cancel_requested" not in columns:
        op.add_column(
            "jobs",
            sa.Column(
                "cancel_requested", sa.Boolean(), nullable=False,
                server_default=sa.false(),
            ),
        )


def downgrade():
    columns = {item["name"] for item in sa.inspect(op.get_bind()).get_columns("jobs")}
    if "cancel_requested" in columns:
        op.drop_column("jobs", "cancel_requested")
