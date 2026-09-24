"""create draft_proposals table

Revision ID: 20260924_create_draft_proposals
Revises: 20260922_drop_uq_stock_reservation_source
Create Date: 2026-09-24 12:00:00

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260924_create_draft_proposals"
down_revision = "20260922_drop_uq_stock_reservation_source"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "draft_proposals",
        sa.Column("proposal_id", sa.String(64), primary_key=True),
        sa.Column("proposal_type", sa.String(64), nullable=False),
        sa.Column("sku_code", sa.String(64), nullable=False),
        sa.Column("current_quantity", sa.Integer(), nullable=True),
        sa.Column("proposed_quantity", sa.Integer(), nullable=True),
        sa.Column("adjustment", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("requested_by", sa.String(64), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT_PROPOSAL"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_draft_proposals_sku_code", "draft_proposals", ["sku_code"])
    op.create_index("ix_draft_proposals_status", "draft_proposals", ["status"])
    op.create_index("ix_draft_proposals_requested_by", "draft_proposals", ["requested_by"])
    op.create_index("ix_draft_proposals_created_at", "draft_proposals", ["created_at"])


def downgrade():
    op.drop_index("ix_draft_proposals_created_at", table_name="draft_proposals")
    op.drop_index("ix_draft_proposals_requested_by", table_name="draft_proposals")
    op.drop_index("ix_draft_proposals_status", table_name="draft_proposals")
    op.drop_index("ix_draft_proposals_sku_code", table_name="draft_proposals")
    op.drop_table("draft_proposals")
