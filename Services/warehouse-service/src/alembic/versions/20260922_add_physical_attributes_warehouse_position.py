"""Add physical and operational attributes to Warehouse and Position

Revision ID: 20260922_add_physical_attributes_warehouse_position
Revises:
Create Date: 2026-09-22 17:30:00

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260922_add_physical_attributes_warehouse_position"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Warehouses table columns
    op.add_column("warehouses", sa.Column("warehouse_type", sa.String(50), nullable=False, server_default="ambient"))
    op.add_column("warehouses", sa.Column("capacity_sqm", sa.Float(), nullable=True))
    op.add_column("warehouses", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.add_column("warehouses", sa.Column("manager_id", sa.String(100), nullable=True))
    op.add_column("warehouses", sa.Column("timezone", sa.String(50), nullable=False, server_default="UTC"))

    # Positions table columns
    op.add_column("positions", sa.Column("aisle", sa.String(20), nullable=True))
    op.add_column("positions", sa.Column("bay", sa.String(20), nullable=True))
    op.add_column("positions", sa.Column("level", sa.String(20), nullable=True))
    op.add_column("positions", sa.Column("bin", sa.String(20), nullable=True))
    op.add_column("positions", sa.Column("max_weight_kg", sa.Float(), nullable=True))
    op.add_column("positions", sa.Column("temperature_zone", sa.String(20), nullable=False, server_default="ambient"))
    op.add_column("positions", sa.Column("pick_sequence", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("positions", sa.Column("hazmat_class", sa.String(20), nullable=True))

    op.create_index("ix_positions_pick_sequence", "positions", ["pick_sequence"])


def downgrade():
    op.drop_index("ix_positions_pick_sequence", table_name="positions")
    op.drop_column("positions", "hazmat_class")
    op.drop_column("positions", "pick_sequence")
    op.drop_column("positions", "temperature_zone")
    op.drop_column("positions", "max_weight_kg")
    op.drop_column("positions", "bin")
    op.drop_column("positions", "level")
    op.drop_column("positions", "bay")
    op.drop_column("positions", "aisle")

    op.drop_column("warehouses", "timezone")
    op.drop_column("warehouses", "manager_id")
    op.drop_column("warehouses", "is_active")
    op.drop_column("warehouses", "capacity_sqm")
    op.drop_column("warehouses", "warehouse_type")
