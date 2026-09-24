"""add approval and execution fields to draft_proposals table

Revision ID: 20260924_add_approval_fields
Revises: 20260924_create_draft_proposals
Create Date: 2026-09-24 16:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260924_add_approval_fields"
down_revision = "20260924_create_draft_proposals"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Add Maker-Checker approval and execution tracking columns (TASK-058 / CRIT-08)
    op.add_column("draft_proposals", sa.Column("approved_by", sa.String(64), nullable=True))
    op.add_column("draft_proposals", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("draft_proposals", sa.Column("rejection_reason", sa.Text(), nullable=True))
    op.add_column("draft_proposals", sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("draft_proposals", sa.Column("executed_by", sa.String(64), nullable=True))
    op.add_column("draft_proposals", sa.Column("digital_signature", sa.String(128), nullable=True))

    # 2. Ensure status index exists
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_indexes = [idx["name"] for idx in inspector.get_indexes("draft_proposals")]
    if "ix_draft_proposals_status" not in existing_indexes:
        op.create_index("ix_draft_proposals_status", "draft_proposals", ["status"])


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_indexes = [idx["name"] for idx in inspector.get_indexes("draft_proposals")]
    if "ix_draft_proposals_status" in existing_indexes:
        op.drop_index("ix_draft_proposals_status", table_name="draft_proposals")

    op.drop_column("draft_proposals", "digital_signature")
    op.drop_column("draft_proposals", "executed_by")
    op.drop_column("draft_proposals", "executed_at")
    op.drop_column("draft_proposals", "rejection_reason")
    op.drop_column("draft_proposals", "approved_at")
    op.drop_column("draft_proposals", "approved_by")
