"""Persist explainable clip proposals and human edits.

Revision ID: 0005_clip_candidates
Revises: 0004_transcripts
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_clip_candidates"
down_revision = "0004_transcripts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "clip_candidates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("asset_id", sa.String(36), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("transcript_revision", sa.Integer(), nullable=False),
        sa.Column("analysis_version", sa.String(40), nullable=False),
        sa.Column("start_ms", sa.BigInteger(), nullable=False),
        sa.Column("end_ms", sa.BigInteger(), nullable=False),
        sa.Column("context_start_ms", sa.BigInteger(), nullable=False),
        sa.Column("context_end_ms", sa.BigInteger(), nullable=False),
        sa.Column("word_start_index", sa.Integer(), nullable=False),
        sa.Column("word_end_index", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("reason_codes", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("selected_start_ms", sa.BigInteger(), nullable=True),
        sa.Column("selected_end_ms", sa.BigInteger(), nullable=True),
        sa.Column("aspect", sa.String(20), nullable=False),
        sa.Column("focus_x", sa.Float(), nullable=False),
        sa.Column("focus_y", sa.Float(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_clip_candidates_asset_id", "clip_candidates", ["asset_id"])


def downgrade() -> None:
    op.drop_index("ix_clip_candidates_asset_id", table_name="clip_candidates")
    op.drop_table("clip_candidates")
