"""add owner_id to draft_proposals and stock_reservations for 3PL multi-tenancy

Revision ID: 20260925_add_owner_id_3pl
Revises: 20260925_add_warehouse_and_location
Create Date: 2026-09-25 15:00:00

TASK-082 / CRIT-04 & EDGE-02:
Add owner_id to draft_proposals and stock_reservations tables
to support 3PL client isolation and multi-tenant soft quarantine.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260925_add_owner_id_3pl"
down_revision = "20260925_add_warehouse_and_location"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Add owner_id to draft_proposals
    op.add_column(
        "draft_proposals",
        sa.Column("owner_id", sa.String(100), nullable=False, server_default="DEFAULT_OWNER"),
    )
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_indexes_dp = [idx["name"] for idx in inspector.get_indexes("draft_proposals")]
    if "ix_draft_proposals_owner_id" not in existing_indexes_dp:
        op.create_index("ix_draft_proposals_owner_id", "draft_proposals", ["owner_id"])

    # 2. Add owner_id to stock_reservations
    op.add_column(
        "stock_reservations",
        sa.Column("owner_id", sa.String(100), nullable=False, server_default="DEFAULT_OWNER"),
    )
    existing_indexes_sr = [idx["name"] for idx in inspector.get_indexes("stock_reservations")]
    if "ix_stock_reservations_owner_id" not in existing_indexes_sr:
        op.create_index("ix_stock_reservations_owner_id", "stock_reservations", ["owner_id"])


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    existing_indexes_sr = [idx["name"] for idx in inspector.get_indexes("stock_reservations")]
    if "ix_stock_reservations_owner_id" in existing_indexes_sr:
        op.drop_index("ix_stock_reservations_owner_id", table_name="stock_reservations")
    op.drop_column("stock_reservations", "owner_id")

    existing_indexes_dp = [idx["name"] for idx in inspector.get_indexes("draft_proposals")]
    if "ix_draft_proposals_owner_id" in existing_indexes_dp:
        op.drop_index("ix_draft_proposals_owner_id", table_name="draft_proposals")
    op.drop_column("draft_proposals", "owner_id")
