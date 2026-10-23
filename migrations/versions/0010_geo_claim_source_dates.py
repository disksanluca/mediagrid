"""Keep source publication dates distinct from the time an API was checked.

Revision ID: 0010_geo_claim_source_dates
Revises: 0009_job_leases
"""

import sqlalchemy as sa
from alembic import op

revision = "0010_geo_claim_source_dates"
down_revision = "0009_job_leases"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("knowledge_claims") as batch:
        batch.alter_column("published_at", existing_type=sa.Date(), nullable=True)
        batch.add_column(sa.Column("source_checked_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    # Older schemas require a publication date. A checked date is only a
    # compatibility fallback during an explicit rollback, never an assertion
    # that the source published on that day.
    bind = op.get_bind()
    missing = bind.execute(sa.text(
        "SELECT count(*) FROM knowledge_claims WHERE published_at IS NULL"
    )).scalar_one()
    if missing:
        raise RuntimeError("Cannot downgrade: claims without publication dates exist")
    with op.batch_alter_table("knowledge_claims") as batch:
        batch.drop_column("source_checked_at")
        batch.alter_column("published_at", existing_type=sa.Date(), nullable=False)
