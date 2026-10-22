"""Durable local resumable import sessions.

Revision ID: 0003_upload_sessions
Revises: 0002_revisions
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_upload_sessions"
down_revision = "0002_revisions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "upload_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(240), nullable=False),
        sa.Column("media_type", sa.String(40), nullable=False),
        sa.Column("expected_size", sa.BigInteger(), nullable=False),
        sa.Column("expected_sha256", sa.String(64), nullable=True),
        sa.Column("received_bytes", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("rights_status", sa.String(40), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("creator", sa.String(240), nullable=True),
        sa.Column("license_name", sa.String(120), nullable=True),
        sa.Column("commercial_use", sa.Boolean(), nullable=False),
        sa.Column("asset_id", sa.String(36), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("upload_sessions")
