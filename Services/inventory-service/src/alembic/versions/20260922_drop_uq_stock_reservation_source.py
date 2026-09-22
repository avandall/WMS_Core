"""drop uq_stock_reservation_source constraint

Revision ID: 20260922_drop_uq_stock_reservation_source
Revises: 
Create Date: 2026-09-22 15:18:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260922_drop_uq_stock_reservation_source"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    try:
        op.drop_constraint("uq_stock_reservation_source", "stock_reservations", type_="unique")
    except Exception:
        op.drop_index("uq_stock_reservation_source", table_name="stock_reservations")


def downgrade():
    op.create_unique_constraint("uq_stock_reservation_source", "stock_reservations", ["source_type", "source_id"])
