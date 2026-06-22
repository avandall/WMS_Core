from __future__ import annotations

from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[2]
WAREHOUSE_INVENTORY_MODEL = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/infrastructure/models/warehouse_inventory.py"


# ===========================================================================
# Phase 2 – additive DB schema: quantity matrix fields exist in model
# ===========================================================================


class TestWarehouseInventoryModelHasQuantityMatrixFields:
    def test_model_file_contains_physical_qty(self) -> None:
        content = WAREHOUSE_INVENTORY_MODEL.read_text()
        assert "physical_qty" in content

    def test_model_file_contains_reserved_qty(self) -> None:
        content = WAREHOUSE_INVENTORY_MODEL.read_text()
        assert "reserved_qty" in content

    def test_model_file_contains_incoming_qty(self) -> None:
        content = WAREHOUSE_INVENTORY_MODEL.read_text()
        assert "incoming_qty" in content

    def test_model_file_contains_in_transit_qty(self) -> None:
        content = WAREHOUSE_INVENTORY_MODEL.read_text()
        assert "in_transit_qty" in content

    def test_model_file_retains_legacy_quantity_field(self) -> None:
        content = WAREHOUSE_INVENTORY_MODEL.read_text()
        assert "quantity = Column" in content


class TestWarehouseInventoryModelConstraints:
    def test_physical_qty_has_check_constraint(self) -> None:
        content = WAREHOUSE_INVENTORY_MODEL.read_text()
        assert "physical_qty_positive" in content

    def test_reserved_qty_has_check_constraint(self) -> None:
        content = WAREHOUSE_INVENTORY_MODEL.read_text()
        assert "reserved_qty_positive" in content

    def test_incoming_qty_has_check_constraint(self) -> None:
        content = WAREHOUSE_INVENTORY_MODEL.read_text()
        assert "incoming_qty_positive" in content

    def test_in_transit_qty_has_check_constraint(self) -> None:
        content = WAREHOUSE_INVENTORY_MODEL.read_text()
        assert "in_transit_qty_positive" in content


class TestWarehouseInventoryModelIndexes:
    def test_has_product_warehouse_index(self) -> None:
        content = WAREHOUSE_INVENTORY_MODEL.read_text()
        assert "ix_warehouse_inventory_product_warehouse" in content


class TestPhase2BackwardCompatibility:
    def test_legacy_quantity_field_not_removed(self) -> None:
        content = WAREHOUSE_INVENTORY_MODEL.read_text()
        # Ensure the old quantity field is still present
        assert "quantity = Column(Integer, nullable=False, default=0)" in content


class TestPhase2MigrationScriptExists:
    def test_migration_sql_file_exists(self) -> None:
        migration_file = ROOT_DIR / "Services/inventory-service/migrations/phase2_add_quantity_matrix.sql"
        assert migration_file.exists()

    def test_migration_contains_backfill_logic(self) -> None:
        migration_file = ROOT_DIR / "Services/inventory-service/migrations/phase2_add_quantity_matrix.sql"
        content = migration_file.read_text()
        assert "UPDATE warehouse_inventory" in content
        assert "SET physical_qty = quantity" in content

    def test_migration_adds_all_new_fields(self) -> None:
        migration_file = ROOT_DIR / "Services/inventory-service/migrations/phase2_add_quantity_matrix.sql"
        content = migration_file.read_text()
        assert "physical_qty" in content
        assert "reserved_qty" in content
        assert "incoming_qty" in content
        assert "in_transit_qty" in content
