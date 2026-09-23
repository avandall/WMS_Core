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
if inv_src not in sys.path:
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
from app.modules.inventory.infrastructure.models.stock_reservation import StockReservationModel  # noqa: E402
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

    def test_reservation_multi_product_same_document(self, db_session, inventory_repo):
        """TASK-017 Acceptance Criteria:
        - Reserving 5 different products for the same sale document (same source_type & source_id)
          must succeed without IntegrityError.
        - 5 reservation rows must be created in StockReservationModel.
        - Idempotency key uniqueness remains enforced.
        """
        from sqlalchemy.exc import IntegrityError

        warehouse_id = 1
        doc_id = 9999
        products = [101, 102, 103, 104, 105]

        # 1. Seed stock for 5 products in warehouse 1 so ATP check passes
        for pid in products:
            inventory_repo.adjust_location_quantity(
                warehouse_id=warehouse_id,
                position_id=1,
                product_id=pid,
                quantity_delta=100,
                allocated_delta=0,
                lpn=f"PALLET-{pid}",
                status="AVAILABLE",
            )

        # 2. Call create_reservation for each product under the same document
        reservation_ids = []
        for pid in products:
            event_id = f"doc_{doc_id}_product_{pid}"
            res_id = inventory_repo.create_reservation(
                source_type="sale_document",
                source_id=doc_id,
                document_id=doc_id,
                product_id=pid,
                warehouse_id=warehouse_id,
                requested_qty=10,
                created_by="test_user",
                idempotency_key=event_id,
                expires_at=None,
            )
            reservation_ids.append(res_id)

        # 3. Verify 5 distinct reservation rows were created
        assert len(reservation_ids) == 5
        assert len(set(reservation_ids)) == 5

        reservations = db_session.query(StockReservationModel).filter(
            StockReservationModel.source_type == "sale_document",
            StockReservationModel.source_id == doc_id,
        ).all()
        assert len(reservations) == 5

        # 4. Verify idempotency protection: reusing existing idempotency_key returns existing reservation ID
        first_pid = products[0]
        duplicate_res_id = inventory_repo.create_reservation(
            source_type="sale_document",
            source_id=doc_id,
            document_id=doc_id,
            product_id=first_pid,
            warehouse_id=warehouse_id,
            requested_qty=10,
            created_by="test_user",
            idempotency_key=f"doc_{doc_id}_product_{first_pid}",
            expires_at=None,
        )
        assert duplicate_res_id == reservation_ids[0]

        # 5. Verify direct insertion of duplicate idempotency_key triggers IntegrityError
        dup_model = StockReservationModel(
            source_type="sale_document",
            source_id=doc_id,
            document_id=doc_id,
            product_id=999,
            warehouse_id=warehouse_id,
            requested_qty=5,
            reserved_qty=5,
            status="RESERVED",
            idempotency_key=f"doc_{doc_id}_product_{first_pid}",
        )
        db_session.add(dup_model)
        with pytest.raises(IntegrityError):
            db_session.flush()
        db_session.rollback()

    def test_total_quantity_equals_sum_of_warehouses(self, inventory_service, inventory_repo):
        """TASK-030 Acceptance Criteria:
        Adjust 2 warehouse quantities separately, total quantity must equal the sum of warehouse physical quantities.
        """
        product_id = 999
        # Adjust 50 units in Warehouse 1
        inventory_service.adjust_inventory(
            product_id=product_id, quantity_delta=50, warehouse_id=1
        )
        # Adjust 30 units in Warehouse 2
        inventory_service.adjust_inventory(
            product_id=product_id, quantity_delta=30, warehouse_id=2
        )

        total_qty = inventory_service.get_total_quantity(product_id)
        assert total_qty == 80  # 50 + 30

        repo_qty = inventory_repo.get_quantity(product_id)
        assert repo_qty == 80

        status = inventory_service.get_inventory_status(product_id)
        assert status["total_quantity"] == 80

    def test_transfer_preserves_total_inventory(self, inventory_service, inventory_repo):
        """TASK-025 Acceptance Criteria:
        - TRANSFER_RECEIPT updates destination location stock (inventory_locations).
        - Aggregate query get_quantity(product_id) returns SUM(warehouse_inventory.physical_qty) unchanged before and after transfer.
        """
        product_id = 888
        src_wh = 1
        dst_wh = 2
        src_pos = 101
        dst_pos = 201

        # 1. Seed initial stock at Warehouse 1, Position 101 (100 units)
        inventory_service.adjust_location_inventory(
            warehouse_id=src_wh,
            position_id=src_pos,
            product_id=product_id,
            quantity_delta=100,
            lpn="PALLET-SRC",
            lot_number="LOT-001",
        )

        initial_total = inventory_service.get_total_quantity(product_id)
        assert initial_total == 100

        # Verify initial location stock
        src_locs = inventory_service.get_inventory_locations(
            warehouse_id=src_wh, product_id=product_id, position_id=src_pos
        )
        assert len(src_locs) == 1
        assert src_locs[0]["quantity"] == 100

        # 2. Execute TRANSFER_ISSUE (issue 40 units from Warehouse 1 Position 101)
        inventory_service.confirm_inventory_transaction(
            transaction_type="TRANSFER_ISSUE",
            product_id=product_id,
            warehouse_id=src_wh,
            quantity=40,
            position_id=src_pos,
            lpn="PALLET-SRC",
            lot_number="LOT-001",
            idempotency_key="transfer_issue_888",
        )

        # Source location stock reduced to 60
        src_locs_after = inventory_service.get_inventory_locations(
            warehouse_id=src_wh, product_id=product_id, position_id=src_pos
        )
        assert src_locs_after[0]["quantity"] == 60

        # 3. Execute TRANSFER_RECEIPT at Warehouse 2 Position 201 (40 units)
        inventory_service.confirm_inventory_transaction(
            transaction_type="TRANSFER_RECEIPT",
            product_id=product_id,
            warehouse_id=dst_wh,
            source_warehouse_id=src_wh,
            quantity=40,
            position_id=dst_pos,
            lpn="PALLET-DST",
            lot_number="LOT-001",
            idempotency_key="transfer_receipt_888",
        )

        # 4. Verify TRANSFER_RECEIPT updated destination location stock (inventory_locations)
        dst_locs = inventory_service.get_inventory_locations(
            warehouse_id=dst_wh, product_id=product_id, position_id=dst_pos
        )
        assert len(dst_locs) == 1
        assert dst_locs[0]["quantity"] == 40
        assert dst_locs[0]["warehouse_id"] == dst_wh
        assert dst_locs[0]["position_id"] == dst_pos
        assert dst_locs[0]["lpn"] == "PALLET-DST"

        # 5. Verify aggregate get_quantity returns SUM(warehouse_inventory.physical_qty) unchanged (100)
        final_total = inventory_service.get_total_quantity(product_id)
        assert final_total == 100  # 60 (Wh 1) + 40 (Wh 2) = 100

        repo_total = inventory_repo.get_quantity(product_id)
        assert repo_total == 100

        # Also test apply_document_movement with doc_type="TRANSFER"
        doc_product_id = 777
        inventory_service.adjust_location_inventory(
            warehouse_id=src_wh,
            position_id=10,
            product_id=doc_product_id,
            quantity_delta=100,
            lpn="PALLET-DOC-SRC",
        )
        assert inventory_service.get_total_quantity(doc_product_id) == 100

        inventory_service.apply_document_movement({
            "event_id": "transfer_doc_evt_777",
            "doc_type": "TRANSFER",
            "document_id": 5001,
            "from_warehouse_id": src_wh,
            "to_warehouse_id": dst_wh,
            "items": [
                {
                    "product_id": doc_product_id,
                    "quantity": 30,
                    "from_position_id": 10,
                    "to_position_id": 20,
                    "from_lpn": "PALLET-DOC-SRC",
                    "to_lpn": "PALLET-DOC-DST",
                }
            ],
        })

        assert inventory_service.get_total_quantity(doc_product_id) == 100
        dst_doc_locs = inventory_service.get_inventory_locations(
            warehouse_id=dst_wh, product_id=doc_product_id, position_id=20
        )
        assert len(dst_doc_locs) == 1
        assert dst_doc_locs[0]["quantity"] == 30


class TestTask039AcceptanceCriteria:
    """Acceptance criteria unit tests for TASK-039:
    - Timezone UTC consistency
    - Suppress READ events on ListInventoryItems
    - Guard release_reservation when reserved_qty == 0
    """

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

    def test_timezone_consistency(self):
        from datetime import datetime, timezone
        from app.shared.utils.domain import DateUtils

        now_utc = DateUtils.get_current_datetime()
        assert now_utc.tzinfo is not None
        assert now_utc.tzinfo == timezone.utc

    def test_list_inventory_no_event(self):
        from unittest.mock import MagicMock
        from inventory_service.grpc_servicer import InventoryServiceServicer

        servicer = InventoryServiceServicer()
        publisher = MagicMock()
        servicer._publisher = publisher

        # Mock service return
        mock_item = MagicMock()
        mock_item.product_id = 1
        mock_item.quantity = 100
        mock_service = MagicMock()
        mock_service.get_all_inventory_items.return_value = [mock_item]

        servicer._service = MagicMock(return_value=mock_service)

        ctx = MagicMock()
        request = MagicMock()

        response = servicer.ListInventoryItems(request, ctx)
        assert len(response.items) == 1
        assert publisher.publish.call_count == 0

    def test_release_reservation_zero_guard(self, inventory_service, inventory_repo):
        """Verify release_reservation returns early without error when reserved_qty is 0 or status is RELEASED."""
        inventory_service.adjust_inventory(
            product_id=10,
            quantity_delta=10,
            warehouse_id=1,
        )

        res_id = inventory_service.reserve_stock(
            source_type="test",
            source_id=1,
            document_id=1,
            product_id=10,
            warehouse_id=1,
            quantity=5,
        )

        # Release first time
        result1 = inventory_service.release_reservation(reservation_id=res_id)
        assert result1 is True

        res = inventory_repo.get_reservation(res_id)
        assert res["status"] == "RELEASED"

        # Release second time (reserved_qty is now 0 and status is RELEASED)
        result2 = inventory_service.release_reservation(reservation_id=res_id)
        assert result2 is True


class TestTask034AcceptanceCriteria:
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

    def test_inventory_status_allocated_quantity_correct(self, inventory_service, inventory_repo):
        """TASK-034 Acceptance Criteria:
        - allocated_quantity = SUM(reserved_qty + allocated_qty).
        - unallocated_quantity = total_quantity - allocated_quantity.
        - Verify get_inventory_status returns accurate allocated_quantity and unallocated_quantity.
        """
        product_id = 777
        warehouse_id = 1

        # 1. Adjust initial physical stock (100 units)
        inventory_service.adjust_inventory(
            product_id=product_id,
            quantity_delta=100,
            warehouse_id=warehouse_id,
        )

        # Before reservation: total=100, allocated=0, unallocated=100
        status_before = inventory_service.get_inventory_status(product_id)
        assert status_before["total_quantity"] == 100
        assert status_before["allocated_quantity"] == 0
        assert status_before["unallocated_quantity"] == 100

        # 2. Reserve 30 units
        res_id = inventory_service.reserve_stock(
            source_type="order",
            source_id=101,
            document_id=201,
            product_id=product_id,
            warehouse_id=warehouse_id,
            quantity=30,
        )
        assert res_id > 0

        # After reservation: total=100, allocated=30, unallocated=70
        status_after = inventory_service.get_inventory_status(product_id)
        assert status_after["total_quantity"] == 100
        assert status_after["allocated_quantity"] == 30
        assert status_after["unallocated_quantity"] == 70

    def test_get_all_inventory_batch_query(self, inventory_service, inventory_repo):
        """
        TASK-038 Requirement:
        get_all_inventory_with_details must fetch inventory details using batch queries
        (max 3 queries total) instead of calling per-product N+1 queries.
        """
        inventory_service.adjust_inventory(product_id=1, quantity_delta=100, warehouse_id=1)
        inventory_service.adjust_inventory(product_id=1, quantity_delta=50, warehouse_id=2)
        inventory_service.adjust_inventory(product_id=2, quantity_delta=200, warehouse_id=1)
        inventory_service.adjust_inventory(product_id=3, quantity_delta=300, warehouse_id=2)

        from unittest.mock import MagicMock
        inventory_repo.get_quantity = MagicMock(side_effect=Exception("N+1 get_quantity called"))
        inventory_repo.get_warehouse_distribution = MagicMock(side_effect=Exception("N+1 get_warehouse_distribution called"))

        details = inventory_service.get_all_inventory_with_details()

        assert len(details) == 3
        p1 = next(d for d in details if d["product_id"] == 1)
        assert p1["total_quantity"] == 150
        assert p1["warehouse_count"] == 2

        p2 = next(d for d in details if d["product_id"] == 2)
        assert p2["total_quantity"] == 200
        assert p2["warehouse_count"] == 1

        p3 = next(d for d in details if d["product_id"] == 3)
        assert p3["total_quantity"] == 300
        assert p3["warehouse_count"] == 1






