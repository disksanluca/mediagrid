"""Persist local MusicBrainz draft schedules and fenced worker attempts.

Revision ID: 0011_music_draft_schedule
Revises: 0010_geo_claim_source_dates
"""

import sqlalchemy as sa
from alembic import op

revision = "0011_music_draft_schedule"
down_revision = "0010_geo_claim_source_dates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "music_draft_schedules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("channel_id", sa.String(36), sa.ForeignKey("channels.id"), nullable=False),
        sa.Column("release_group_id", sa.String(36), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("run_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("lease_token", sa.String(64), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("channel_id", "release_group_id", "scheduled_at",
                            name="uq_music_draft_schedule"),
        sa.UniqueConstraint("project_id", name="uq_music_draft_project"),
    )
    for column in ("channel_id", "scheduled_at", "run_after", "status"):
        op.create_index(f"ix_music_draft_schedules_{column}",
                        "music_draft_schedules", [column])


def downgrade() -> None:
    count = op.get_bind().execute(sa.text(
        "SELECT count(*) FROM music_draft_schedules WHERE project_id IS NOT NULL"
    )).scalar_one()
    if count:
        raise RuntimeError("Cannot downgrade: scheduled music projects exist")
    op.drop_table("music_draft_schedules")
