"""Persist locally generated words and human-reviewed caption cues.

Revision ID: 0004_transcripts
Revises: 0003_upload_sessions
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_transcripts"
down_revision = "0003_upload_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "transcripts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("asset_id", sa.String(36), sa.ForeignKey("assets.id"), unique=True),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("engine", sa.String(40), nullable=False),
        sa.Column("model_id", sa.String(240), nullable=False),
        sa.Column("model_version", sa.String(40), nullable=False),
        sa.Column("language", sa.String(20), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("cues_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "transcript_words",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("transcript_id", sa.String(36), sa.ForeignKey("transcripts.id"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("start_ms", sa.BigInteger(), nullable=False),
        sa.Column("end_ms", sa.BigInteger(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("speaker_id", sa.String(80), nullable=True),
        sa.Column("edited", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_transcript_words_transcript_id", "transcript_words", ["transcript_id"])


def downgrade() -> None:
    op.drop_index("ix_transcript_words_transcript_id", table_name="transcript_words")
    op.drop_table("transcript_words")
    op.drop_table("transcripts")
