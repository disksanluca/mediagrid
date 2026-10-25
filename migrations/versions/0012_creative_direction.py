"""Persist Creative Director revisions without changing legacy project or EDL data.

Revision ID: 0012_creative_direction
Revises: 0011_music_draft_schedule
"""

import sqlalchemy as sa
from alembic import op

revision = "0012_creative_direction"
down_revision = "0011_music_draft_schedule"
branch_labels = None
depends_on = None


def _revision_table(name: str, owner: str, unique: str) -> None:
    op.create_table(
        name,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(owner, sa.String(36), sa.ForeignKey(
            "channels.id" if owner == "channel_id" else "projects.id"
        ), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(owner, "revision", name=unique),
        sa.CheckConstraint("revision >= 1", name=f"ck_{name}_revision_positive"),
    )
    op.create_index(f"ix_{name}_{owner}", name, [owner])


def upgrade() -> None:
    _revision_table("creative_dna_revisions", "channel_id", "uq_creative_dna_revision")
    _revision_table("creative_briefs", "project_id", "uq_creative_brief_revision")
    op.create_table(
        "creative_direction_sets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("brief_sha256", sa.String(64), nullable=False),
        sa.Column("dna_sha256", sa.String(64), nullable=False),
        sa.Column("origin", sa.String(40), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "revision", name="uq_creative_directions_revision"),
        sa.CheckConstraint("revision >= 1", name="ck_creative_directions_revision_positive"),
    )
    op.create_index(
        "ix_creative_direction_sets_project_id", "creative_direction_sets", ["project_id"]
    )
    op.create_table(
        "creative_storyboard_revisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "direction_set_id", sa.String(36), sa.ForeignKey("creative_direction_sets.id"),
            nullable=False,
        ),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "revision", name="uq_creative_storyboard_revision"),
        sa.CheckConstraint("revision >= 1", name="ck_creative_storyboard_revision_positive"),
    )
    op.create_index(
        "ix_creative_storyboard_revisions_project_id", "creative_storyboard_revisions",
        ["project_id"],
    )
    op.create_table(
        "creative_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("storyboard_revision", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("actor", sa.String(120), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("snapshot_sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "revision", name="uq_creative_review_revision"),
        sa.CheckConstraint("revision >= 1", name="ck_creative_review_revision_positive"),
    )
    op.create_index("ix_creative_reviews_project_id", "creative_reviews", ["project_id"])


def downgrade() -> None:
    for name in (
        "creative_reviews", "creative_storyboard_revisions", "creative_direction_sets",
        "creative_briefs", "creative_dna_revisions",
    ):
        count = op.get_bind().execute(sa.text(f"SELECT count(*) FROM {name}")).scalar_one()
        if count:
            raise RuntimeError(f"Cannot downgrade: {name} contains creative revisions")
    for name in (
        "creative_reviews", "creative_storyboard_revisions", "creative_direction_sets",
        "creative_briefs", "creative_dna_revisions",
    ):
        op.drop_table(name)
