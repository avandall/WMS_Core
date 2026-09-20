"""
Unit tests for Inventory Location management & InventoryService
Covers TASK-002 Acceptance Criteria:
- InventoryLocation domain entity & model
- Querying exact location: SKU A at Bin/Position B, Pallet/LPN C
- Auto-sync to warehouse_inventory Read-Model / summary cache
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
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.shared.core.database import Base  # noqa: E402
from app.modules.inventory.domain.entities.inventory_location import (  # noqa: E402
    InventoryLocation,
)
from app.shared.domain.business_exceptions import (  # noqa: E402
    InsufficientStockError,
    InvalidQuantityError,
)
from app.modules.inventory.infrastructure.models.warehouse_inventory import WarehouseInventoryModel  # noqa: E402
from app.modules.inventory.infrastructure.repositories.inventory_repo import InventoryRepo  # noqa: E402
from app.modules.inventory.application.services.inventory_service import InventoryService  # noqa: E402



class TestInventoryLocationDomainEntity:
    """Test InventoryLocation domain entity logic and validations."""

    def test_create_valid_location_entity(self):
        loc = InventoryLocation(
            id=1,
            warehouse_id=10,
            position_id=100,
            product_id=500,
            lpn="PALLET-001",
            quantity=50,
            allocated_qty=10,
            status="AVAILABLE",
        )
        assert loc.warehouse_id == 10
        assert loc.position_id == 100
        assert loc.product_id == 500
        assert loc.lpn == "PALLET-001"
        assert loc.quantity == 50
        assert loc.allocated_qty == 10
        assert loc.available_qty == 40
        assert loc.status == "AVAILABLE"
        assert loc.identity == 1

    def test_invalid_negative_quantity_raises_error(self):
        with pytest.raises(InvalidQuantityError):
            InventoryLocation(warehouse_id=1, position_id=1, product_id=1, quantity=-5)

    def test_invalid_allocated_exceeds_quantity_raises_error(self):
        with pytest.raises(InvalidQuantityError):
            InventoryLocation(warehouse_id=1, position_id=1, product_id=1, quantity=10, allocated_qty=15)

    def test_invalid_status_raises_error(self):
        with pytest.raises(ValueError):
            InventoryLocation(warehouse_id=1, position_id=1, product_id=1, status="UNKNOWN_STATUS")

    def test_add_and_remove_stock(self):
        loc = InventoryLocation(warehouse_id=1, position_id=1, product_id=1, quantity=20)
        loc.add_stock(30)
        assert loc.quantity == 50

        loc.remove_stock(15)
        assert loc.quantity == 35

    def test_remove_stock_exceeds_available_raises_error(self):
        loc = InventoryLocation(warehouse_id=1, position_id=1, product_id=1, quantity=20, allocated_qty=15)
        with pytest.raises(InsufficientStockError):
            loc.remove_stock(10)  # Available is only 5

    def test_allocate_and_release_stock(self):
        loc = InventoryLocation(warehouse_id=1, position_id=1, product_id=1, quantity=100)
        loc.allocate_stock(30)
        assert loc.allocated_qty == 30
        assert loc.available_qty == 70

        loc.release_allocation(10)
        assert loc.allocated_qty == 20
        assert loc.available_qty == 80

    def test_update_status(self):
        loc = InventoryLocation(warehouse_id=1, position_id=1, product_id=1, quantity=10)
        loc.update_status("QUARANTINED")
        assert loc.status == "QUARANTINED"
        loc.update_status("DAMAGED")
        assert loc.status == "DAMAGED"


class TestInventoryLocationRepositoryIntegration:
    """Test InventoryRepo location-level persistence and warehouse_inventory summary cache."""

    @pytest.fixture
    def db_session(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        yield session
        session.close()

    @pytest.fixture
    def inventory_repo(self, db_session):
        return InventoryRepo(db_session)

    @pytest.fixture
    def inventory_service(self, inventory_repo):
        return InventoryService(inventory_repo)

    def test_adjust_location_quantity_and_summary_cache_sync(self, db_session, inventory_repo):
        # 1. Adjust location stock for Product 500 at Warehouse 1, Position 101, LPN PALLET-A
        res1 = inventory_repo.adjust_location_quantity(
            warehouse_id=1,
            position_id=101,
            product_id=500,
            quantity_delta=100,
            allocated_delta=20,
            lpn="PALLET-A",
            status="AVAILABLE",
        )
        assert res1["warehouse_id"] == 1
        assert res1["position_id"] == 101
        assert res1["product_id"] == 500
        assert res1["lpn"] == "PALLET-A"
        assert res1["quantity"] == 100
        assert res1["allocated_qty"] == 20
        assert res1["available_qty"] == 80

        # 2. Adjust location stock for SAME product at Warehouse 1, Position 102, LPN PALLET-B
        res2 = inventory_repo.adjust_location_quantity(
            warehouse_id=1,
            position_id=102,
            product_id=500,
            quantity_delta=50,
            allocated_delta=10,
            lpn="PALLET-B",
            status="AVAILABLE",
        )
        assert res2["quantity"] == 50

        # 3. Verify warehouse_inventory summary table (Read-Model) is automatically synced
        wh_summary = db_session.query(WarehouseInventoryModel).filter_by(
            warehouse_id=1, product_id=500
        ).first()
        assert wh_summary is not None
        assert wh_summary.quantity == 150  # 100 + 50
        assert wh_summary.physical_qty == 150
        assert wh_summary.reserved_qty == 30  # 20 + 10

    def test_query_exact_location_bin_and_pallet(self, inventory_service):
        # Add 3 locations
        inventory_service.adjust_location_inventory(
            warehouse_id=1, position_id=10, product_id=100, quantity_delta=40, lpn="PALLET-X"
        )
        inventory_service.adjust_location_inventory(
            warehouse_id=1, position_id=20, product_id=100, quantity_delta=60, lpn="PALLET-Y"
        )
        inventory_service.adjust_location_inventory(
            warehouse_id=1, position_id=10, product_id=200, quantity_delta=15, lpn="PALLET-Z"
        )

        # Query SKU 100 at Position 10, Pallet-X
        locs = inventory_service.get_inventory_locations(
            warehouse_id=1, product_id=100, position_id=10, lpn="PALLET-X"
        )
        assert len(locs) == 1
        assert locs[0]["product_id"] == 100
        assert locs[0]["position_id"] == 10
        assert locs[0]["lpn"] == "PALLET-X"
        assert locs[0]["quantity"] == 40

        # Query all locations for SKU 100 in Warehouse 1
        all_sku100_locs = inventory_service.get_inventory_locations(
            warehouse_id=1, product_id=100
        )
        assert len(all_sku100_locs) == 2
