"""
Unit tests for InventoryRepo — TASK-018
Covers:
- sync_warehouse_inventory_summary preserves active reservation in warehouse_inventory.reserved_qty
- reserved_qty is loaded from StockReservationModel (status='RESERVED') and not overwritten by location allocated_qty
- Available stock ATP calculation
"""

import sys
from pathlib import Path

# Purge any previously imported 'app' module to avoid cross-service namespace collisions
for mod in list(sys.modules.keys()):
    if mod == "app" or mod.startswith("app."):
        del sys.modules[mod]

inv_src = str(Path(__file__).resolve().parent.parent.parent.parent / "Services" / "inventory-service" / "src")
sys.path = [p for p in sys.path if "/Services/" not in p]
sys.path.insert(0, inv_src)

import pytest  # noqa: E402
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.shared.core.database import Base  # noqa: E402
from app.modules.inventory.infrastructure.models.warehouse_inventory import WarehouseInventoryModel  # noqa: E402
from app.modules.inventory.infrastructure.repositories.inventory_repo import InventoryRepo  # noqa: E402


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def inventory_repo(db_session):
    return InventoryRepo(db_session)


class TestInventoryRepoSyncReservation:


    def test_sync_preserves_reservation(self, db_session, inventory_repo):
        """
        Verify that after adjust_location_quantity runs (which calls sync_warehouse_inventory_summary),
        warehouse_inventory.reserved_qty is NOT reset to 0 or overwritten with location allocated_qty
        when there is an active reservation in StockReservationModel.
        """
        warehouse_id = 1
        product_id = 100

        # 1. Adjust initial location quantity: 100 units at position 101 with 0 allocated
        inventory_repo.adjust_location_quantity(
            warehouse_id=warehouse_id,
            position_id=101,
            product_id=product_id,
            quantity_delta=100,
            allocated_delta=0,
        )

        wh_inv = db_session.execute(
            select(WarehouseInventoryModel).where(
                WarehouseInventoryModel.warehouse_id == warehouse_id,
                WarehouseInventoryModel.product_id == product_id,
            )
        ).scalar_one()

        assert wh_inv.physical_qty == 100
        assert wh_inv.reserved_qty == 0

        # 2. Create an active stock reservation for 30 units
        res_id = inventory_repo.create_reservation(
            source_type="sales_order",
            source_id=1001,
            document_id=2001,
            product_id=product_id,
            warehouse_id=warehouse_id,
            requested_qty=30,
            created_by="test_user",
            idempotency_key="res-key-001",
            expires_at=None,
        )
        assert res_id > 0

        wh_inv_after_res = db_session.execute(
            select(WarehouseInventoryModel).where(
                WarehouseInventoryModel.warehouse_id == warehouse_id,
                WarehouseInventoryModel.product_id == product_id,
            )
        ).scalar_one()

        assert wh_inv_after_res.reserved_qty == 30
        assert wh_inv_after_res.physical_qty == 100

        # 3. Perform a location quantity adjustment (e.g. allocating 10 units at bin level for picking)
        inventory_repo.adjust_location_quantity(
            warehouse_id=warehouse_id,
            position_id=101,
            product_id=product_id,
            quantity_delta=0,
            allocated_delta=10,
        )

        # 4. Check warehouse_inventory: reserved_qty MUST STILL BE 30 (active reservation), NOT 10 (allocated_qty) or 0
        wh_inv_after_sync = db_session.execute(
            select(WarehouseInventoryModel).where(
                WarehouseInventoryModel.warehouse_id == warehouse_id,
                WarehouseInventoryModel.product_id == product_id,
            )
        ).scalar_one()

        assert wh_inv_after_sync.reserved_qty == 30
        assert wh_inv_after_sync.physical_qty == 100

        # 5. Check calculate_available_stock
        avail = inventory_repo.calculate_available_stock(product_id=product_id, warehouse_id=warehouse_id)
        assert avail["physical_qty"] == 100
        assert avail["reserved_qty"] == 30
        assert avail["available_qty"] == 70  # 100 - 30

    def test_sync_reflects_multiple_active_reservations(self, db_session, inventory_repo):
        warehouse_id = 1
        product_id = 200

        # Seed initial location stock
        inventory_repo.adjust_location_quantity(
            warehouse_id=warehouse_id,
            position_id=50,
            product_id=product_id,
            quantity_delta=500,
        )

        # Create two separate reservations
        inventory_repo.create_reservation(
            source_type="order",
            source_id=1,
            document_id=None,
            product_id=product_id,
            warehouse_id=warehouse_id,
            requested_qty=50,
            created_by="user1",
            idempotency_key="key-1",
            expires_at=None,
        )
        inventory_repo.create_reservation(
            source_type="order",
            source_id=2,
            document_id=None,
            product_id=product_id,
            warehouse_id=warehouse_id,
            requested_qty=25,
            created_by="user2",
            idempotency_key="key-2",
            expires_at=None,
        )

        # Force explicit sync call
        inventory_repo.sync_warehouse_inventory_summary(warehouse_id, product_id)

        wh_inv = db_session.execute(
            select(WarehouseInventoryModel).where(
                WarehouseInventoryModel.warehouse_id == warehouse_id,
                WarehouseInventoryModel.product_id == product_id,
            )
        ).scalar_one()

        assert wh_inv.reserved_qty == 75  # 50 + 25
        assert wh_inv.physical_qty == 500


def test_sync_preserves_reservation(db_session, inventory_repo):
    """Top-level test entrypoint for test_sync_preserves_reservation."""
    tester = TestInventoryRepoSyncReservation()
    tester.test_sync_preserves_reservation(db_session, inventory_repo)


