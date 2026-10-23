"""Store human-reviewed, source-linked factual claims.

Revision ID: 0007_knowledge_claims
Revises: 0006_football_sequences
"""

import sqlalchemy as sa
from alembic import op

revision = "0007_knowledge_claims"
down_revision = "0006_football_sequences"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_claims",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("scene_id", sa.String(100), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_title", sa.String(240), nullable=False),
        sa.Column("published_at", sa.Date(), nullable=False),
        sa.Column("support_excerpt", sa.Text(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_knowledge_claims_project_id", "knowledge_claims", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_claims_project_id", table_name="knowledge_claims")
    op.drop_table("knowledge_claims")
