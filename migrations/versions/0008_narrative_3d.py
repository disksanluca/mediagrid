"""Persist versioned procedural 3D stories and blocking approval.

Revision ID: 0008_narrative_3d
Revises: 0007_knowledge_claims
"""

import sqlalchemy as sa
from alembic import op

revision = "0008_narrative_3d"
down_revision = "0007_knowledge_claims"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "narrative_3d",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"),
                  nullable=False, unique=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("aspect", sa.String(20), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("shots_json", sa.JSON(), nullable=False),
        sa.Column("rig_version", sa.String(40), nullable=False),
        sa.Column("world_version", sa.String(40), nullable=False),
        sa.Column("audio_asset_id", sa.String(36), sa.ForeignKey("assets.id"), nullable=True),
        sa.Column("audio_sha256", sa.String(64), nullable=True),
        sa.Column("blocking_job_id", sa.String(36), nullable=True),
        sa.Column("blocking_sha256", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("narrative_3d")
