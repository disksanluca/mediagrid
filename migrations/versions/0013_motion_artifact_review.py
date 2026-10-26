"""Human review of derived audiovisual artifacts; no timeline or project mutation.

Revision ID: 0013_motion_artifact_review
Revises: 0012_creative_direction
"""

import sqlalchemy as sa
from alembic import op

revision = "0013_motion_artifact_review"
down_revision = "0012_creative_direction"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "motion_artifact_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        *[
            sa.Column(field, sa.String(64), nullable=False)
            for field in (
                "request_sha256",
                "plan_sha256",
                "video_sha256",
                "snapshot_sha256",
                "dependencies_sha256",
            )
        ],
        sa.Column("decision", sa.String(24), nullable=False),
        sa.Column("actor", sa.String(120), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("job_id", "revision", name="uq_motion_artifact_revision"),
        sa.UniqueConstraint("job_id", "request_sha256", name="uq_motion_artifact_request"),
        sa.CheckConstraint("revision >= 1", name="ck_motion_artifact_revision"),
        sa.CheckConstraint(
            "decision IN ('REQUEST_REVIEW', 'APPROVE', 'REJECT')",
            name="ck_motion_artifact_decision",
        ),
    )
    for field in ("project_id", "job_id"):
        op.create_index(f"ix_motion_artifact_reviews_{field}", "motion_artifact_reviews", [field])


def downgrade():
    if op.get_bind().execute(sa.text("SELECT count(*) FROM motion_artifact_reviews")).scalar_one():
        raise RuntimeError(
            "Cannot downgrade: motion_artifact_reviews contains human review history"
        )
    op.drop_table("motion_artifact_reviews")
