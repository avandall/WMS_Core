"""add warehouse and location tracking to draft_proposals table

Revision ID: 20260925_add_warehouse_and_location
Revises: 20260924_add_approval_fields
Create Date: 2026-09-25 10:00:00

TASK-063 / CRIT-01 & CRIT-02:
Add warehouse_id, location_code, and position_id to draft_proposals table
to support multi-warehouse isolation and location-level ledger consistency.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260925_add_warehouse_and_location"
down_revision = "20260924_add_approval_fields"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Add warehouse and location columns
    op.add_column(
        "draft_proposals",
        sa.Column("warehouse_id", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "draft_proposals",
        sa.Column("location_code", sa.String(50), nullable=True),
    )
    op.add_column(
        "draft_proposals",
        sa.Column("position_id", sa.BigInteger(), nullable=True),
    )

    # 2. Add indexes for high-performance multi-warehouse querying
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_indexes = [idx["name"] for idx in inspector.get_indexes("draft_proposals")]
    if "ix_draft_proposals_warehouse_id" not in existing_indexes:
        op.create_index("ix_draft_proposals_warehouse_id", "draft_proposals", ["warehouse_id"])
    if "ix_draft_proposals_location_code" not in existing_indexes:
        op.create_index("ix_draft_proposals_location_code", "draft_proposals", ["location_code"])
    if "ix_draft_proposals_wh_sku" not in existing_indexes:
        op.create_index("ix_draft_proposals_wh_sku", "draft_proposals", ["warehouse_id", "sku_code"])


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_indexes = [idx["name"] for idx in inspector.get_indexes("draft_proposals")]
    if "ix_draft_proposals_wh_sku" in existing_indexes:
        op.drop_index("ix_draft_proposals_wh_sku", table_name="draft_proposals")
    if "ix_draft_proposals_location_code" in existing_indexes:
        op.drop_index("ix_draft_proposals_location_code", table_name="draft_proposals")
    if "ix_draft_proposals_warehouse_id" in existing_indexes:
        op.drop_index("ix_draft_proposals_warehouse_id", table_name="draft_proposals")

    op.drop_column("draft_proposals", "position_id")
    op.drop_column("draft_proposals", "location_code")
    op.drop_column("draft_proposals", "warehouse_id")
