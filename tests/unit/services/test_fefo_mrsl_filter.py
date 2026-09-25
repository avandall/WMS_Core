"""
Unit tests for Minimum Remaining Shelf Life (MRSL) filtering in FEFO Allocation (TASK-077 / DOM-04).

Acceptance Criteria:
1. Bổ sung tham số min_shelf_life_days: int = 30 vào allocate_inventory_fefo và check_availability.
2. Ô kệ có hạn dùng còn lại nhỏ hơn min_shelf_life_days không được cấp phát cho đơn bán hàng.
3. Viết test xác nhận lô hàng còn 10 ngày hạn dùng bị bỏ qua, hệ thống cấp phát lô hàng còn 60 ngày hạn dùng tiếp theo.
"""

from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.modules.inventory.application.services.allocation_service import AllocationService
from app.modules.inventory.application.services.inventory_service import InventoryService
from app.modules.inventory.infrastructure.repositories.inventory_repo import InventoryRepo
from app.shared.core.database import Base, import_all_models
from app.shared.domain.business_exceptions import InsufficientStockError


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    import_all_models()
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_mrsl_filter_skips_10_days_allocates_60_days(db_session):
    """
    TASK-077 / DOM-04 Acceptance Criteria:
    Lô hàng còn 10 ngày hạn dùng bị bỏ qua (MRSL < 30 ngày),
    hệ thống cấp phát lô hàng còn 60 ngày hạn dùng tiếp theo.
    """
    repo = InventoryRepo(db_session)
    alloc_service = AllocationService(repo)

    now = datetime.now(timezone.utc)
    exp_10_days = now + timedelta(days=10)
    exp_60_days = now + timedelta(days=60)
    product_id = 1001
    warehouse_id = 1

    # Bin 1: Lot nearing expiration (10 days remaining) - 20 units
    repo.adjust_location_quantity(
        warehouse_id=warehouse_id,
        position_id=1,
        product_id=product_id,
        quantity_delta=20,
        lpn="LPN-NEAR-10",
        lot_number="LOT-10-DAYS",
        expiry_date=exp_10_days,
    )

    # Bin 2: Fresh lot (60 days remaining) - 20 units
    repo.adjust_location_quantity(
        warehouse_id=warehouse_id,
        position_id=2,
        product_id=product_id,
        quantity_delta=20,
        lpn="LPN-FRESH-60",
        lot_number="LOT-60-DAYS",
        expiry_date=exp_60_days,
    )

    # Request allocation of 15 units with allocate_inventory_fefo (default min_shelf_life_days=30)
    allocations = alloc_service.allocate_inventory_fefo(
        warehouse_id=warehouse_id,
        product_id=product_id,
        quantity=15,
    )

    assert len(allocations) == 1
    # LOT-10-DAYS must be completely skipped
    assert allocations[0]["lot_number"] == "LOT-60-DAYS"
    assert allocations[0]["position_id"] == 2
    assert allocations[0]["allocated_qty"] == 15


def test_check_availability_respects_mrsl_filter(db_session):
    """
    TASK-077: check_availability excludes lots with shelf life < min_shelf_life_days.
    """
    repo = InventoryRepo(db_session)
    alloc_service = AllocationService(repo)

    now = datetime.now(timezone.utc)
    exp_10_days = now + timedelta(days=10)
    exp_60_days = now + timedelta(days=60)
    product_id = 1002
    warehouse_id = 1

    # 25 units with 10 days remaining
    repo.adjust_location_quantity(
        warehouse_id=warehouse_id,
        position_id=1,
        product_id=product_id,
        quantity_delta=25,
        lot_number="LOT-NEAR",
        expiry_date=exp_10_days,
    )

    # 30 units with 60 days remaining
    repo.adjust_location_quantity(
        warehouse_id=warehouse_id,
        position_id=2,
        product_id=product_id,
        quantity_delta=30,
        lot_number="LOT-FRESH",
        expiry_date=exp_60_days,
    )

    # With default min_shelf_life_days=30: only 30 units are eligible
    atp_mrsl = alloc_service.check_availability(
        warehouse_id=warehouse_id,
        product_id=product_id,
        min_shelf_life_days=30,
    )
    assert atp_mrsl == 30

    # With min_shelf_life_days=0: all non-expired stock (55 units) is available
    atp_all = alloc_service.check_availability(
        warehouse_id=warehouse_id,
        product_id=product_id,
        min_shelf_life_days=0,
    )
    assert atp_all == 55


def test_mrsl_insufficient_stock_when_all_lots_below_threshold(db_session):
    """
    When all stock has shelf life < min_shelf_life_days, InsufficientStockError is raised.
    """
    repo = InventoryRepo(db_session)
    alloc_service = AllocationService(repo)

    now = datetime.now(timezone.utc)
    product_id = 1003
    warehouse_id = 1

    # Only lots with 5 and 15 days remaining
    repo.adjust_location_quantity(
        warehouse_id=warehouse_id,
        position_id=1,
        product_id=product_id,
        quantity_delta=50,
        lot_number="LOT-5D",
        expiry_date=now + timedelta(days=5),
    )
    repo.adjust_location_quantity(
        warehouse_id=warehouse_id,
        position_id=2,
        product_id=product_id,
        quantity_delta=50,
        lot_number="LOT-15D",
        expiry_date=now + timedelta(days=15),
    )

    with pytest.raises(InsufficientStockError) as exc_info:
        alloc_service.allocate_inventory_fefo(
            warehouse_id=warehouse_id,
            product_id=product_id,
            quantity=10,
            min_shelf_life_days=30,
        )
    assert "No available stock to allocate" in str(exc_info.value) or "Insufficient stock" in str(exc_info.value)


def test_custom_min_shelf_life_days(db_session):
    """
    Verify customizable min_shelf_life_days thresholds (e.g. 45-day lot with 60-day vs 30-day requirement).
    """
    repo = InventoryRepo(db_session)
    alloc_service = AllocationService(repo)

    now = datetime.now(timezone.utc)
    product_id = 1004
    warehouse_id = 1

    repo.adjust_location_quantity(
        warehouse_id=warehouse_id,
        position_id=1,
        product_id=product_id,
        quantity_delta=20,
        lot_number="LOT-45D",
        expiry_date=now + timedelta(days=45),
    )

    # 1. Requiring 60 days fails (45 < 60)
    with pytest.raises(InsufficientStockError):
        alloc_service.allocate_inventory_fefo(
            warehouse_id=warehouse_id,
            product_id=product_id,
            quantity=10,
            min_shelf_life_days=60,
        )

    # 2. Requiring 30 days succeeds (45 >= 30)
    allocations = alloc_service.allocate_inventory_fefo(
        warehouse_id=warehouse_id,
        product_id=product_id,
        quantity=10,
        min_shelf_life_days=30,
    )
    assert len(allocations) == 1
    assert allocations[0]["lot_number"] == "LOT-45D"
    assert allocations[0]["allocated_qty"] == 10


def test_mrsl_allows_items_without_expiry_date(db_session):
    """
    Non-perishable items with expiry_date=None are not rejected by MRSL filtering.
    """
    repo = InventoryRepo(db_session)
    alloc_service = AllocationService(repo)

    product_id = 1005
    warehouse_id = 1

    repo.adjust_location_quantity(
        warehouse_id=warehouse_id,
        position_id=1,
        product_id=product_id,
        quantity_delta=40,
        lot_number="LOT-NO-EXP",
        expiry_date=None,
    )

    allocations = alloc_service.allocate_inventory_fefo(
        warehouse_id=warehouse_id,
        product_id=product_id,
        quantity=15,
        min_shelf_life_days=30,
    )
    assert len(allocations) == 1
    assert allocations[0]["lot_number"] == "LOT-NO-EXP"
    assert allocations[0]["allocated_qty"] == 15


def test_inventory_service_delegates_allocate_inventory_fefo(db_session):
    """
    Verify InventoryService.allocate_inventory_fefo delegates with min_shelf_life_days.
    """
    repo = InventoryRepo(db_session)
    service = InventoryService(inventory_repo=repo)

    now = datetime.now(timezone.utc)
    product_id = 1006
    warehouse_id = 1

    # 10-day lot
    repo.adjust_location_quantity(
        warehouse_id=warehouse_id,
        position_id=1,
        product_id=product_id,
        quantity_delta=10,
        lot_number="LOT-EXCLUDED",
        expiry_date=now + timedelta(days=10),
    )
    # 90-day lot
    repo.adjust_location_quantity(
        warehouse_id=warehouse_id,
        position_id=2,
        product_id=product_id,
        quantity_delta=10,
        lot_number="LOT-INCLUDED",
        expiry_date=now + timedelta(days=90),
    )

    allocations = service.allocate_inventory_fefo(
        warehouse_id=warehouse_id,
        product_id=product_id,
        quantity=5,
        min_shelf_life_days=30,
    )
    assert len(allocations) == 1
    assert allocations[0]["lot_number"] == "LOT-INCLUDED"
