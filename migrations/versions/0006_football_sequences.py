"""Persist versioned human-marked football sequences.

Revision ID: 0006_football_sequences
Revises: 0005_clip_candidates
"""

import sqlalchemy as sa
from alembic import op

revision = "0006_football_sequences"
down_revision = "0005_clip_candidates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "football_sequences",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"),
                  nullable=False, unique=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("aspect", sa.String(20), nullable=False),
        sa.Column("shots_json", sa.JSON(), nullable=False),
        sa.Column("score_label", sa.String(80), nullable=True),
        sa.Column("score_source_url", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("football_sequences")
