"""
Integration Test Suite for ATP Double-Reservation Elimination (TASK-072 / CRIT-01).

Acceptance Criteria:
1. check_availability calculates ATP without double-deduction:
   ATP = max(0, Total Valid Physical - max(Total Allocated Loc, Doc Reservations) - Quarantine Reserved)
2. Warehouse has 100 units. Order 1 holds 40 units (has both StockReservation RESERVED and allocated_qty at bin).
   Verify ATP returns exactly 60 units (NOT 20 units).
3. Order 2 requests 30 units and allocates successfully without InsufficientStockError.
4. Over-allocation: Order requesting 65 units raises InsufficientStockError because ATP is 60.
5. Soft Quarantine: Adding PENDING_ADJUSTMENT reservation of 10 units drops ATP to 50 (60 - 10).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import pytest
from app.modules.inventory.application.services.allocation_service import (
    AllocationService,
)
from app.modules.inventory.infrastructure.models.draft_proposal import (
    DraftProposalModel,
)
from app.modules.inventory.infrastructure.models.inventory_location import (
    InventoryLocationModel,
)
from app.modules.inventory.infrastructure.models.inventory_transaction import (
    InventoryTransactionModel,
)
from app.modules.inventory.infrastructure.models.movement_ledger import (
    InventoryMovementLedgerModel,
)
from app.modules.inventory.infrastructure.models.position import PositionModel
from app.modules.inventory.infrastructure.models.stock_reservation import (
    StockReservationModel,
)
from app.modules.inventory.infrastructure.models.warehouse_inventory import (
    WarehouseInventoryModel,
)
from app.modules.inventory.infrastructure.repositories.inventory_repo import (
    InventoryRepo,
)
from app.shared.core.database import Base
from app.shared.domain.business_exceptions import InsufficientStockError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def atp_session():
    """Isolated SQLite database setup with complete schema."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        bind=engine,
        tables=[
            WarehouseInventoryModel.__table__,
            InventoryLocationModel.__table__,
            PositionModel.__table__,
            StockReservationModel.__table__,
            DraftProposalModel.__table__,
            InventoryTransactionModel.__table__,
            InventoryMovementLedgerModel.__table__,
        ],
    )
    Session = sessionmaker(bind=engine)
    session = Session()

    # Seed Position
    pos = PositionModel(id=1, warehouse_id=1, code="BIN-A01", type="STORAGE", is_active=1)
    session.add(pos)
    session.commit()

    # Seed 100 units of SKU 501 at Warehouse 1, Position 1
    repo = InventoryRepo(session)
    repo.adjust_location_quantity(
        warehouse_id=1,
        position_id=1,
        product_id=501,
        quantity_delta=100,
        status="AVAILABLE",
    )
    session.commit()

    yield session
    session.close()


def test_atp_eliminates_double_reservation_deficit(atp_session):
    """
    Test Case 1 & 2:
    - 100 physical units.
    - Order 1 has 40 units reserved via StockReservation AND allocated at bin.
    - ATP must be exactly 60 (NOT 20).
    - Order 2 requests 30 units -> succeeds!
    """
    repo = InventoryRepo(atp_session)
    alloc_service = AllocationService(repo)

    # 1. Initial ATP must be 100
    assert alloc_service.check_availability(warehouse_id=1, product_id=501) == 100

    # 2. Simulate Order 1 reserving 40 units:
    # First: StockReservation created (status='RESERVED', reserved_qty=40)
    repo.create_reservation(
        source_type="document",
        source_id=1001,
        document_id=1001,
        product_id=501,
        warehouse_id=1,
        requested_qty=40,
        created_by="SALES_AGENT",
        idempotency_key="order_1001_res",
        expires_at=None,
        status="RESERVED",
    )
    # Second: Location allocated_qty increased by 40 at the bin
    repo.adjust_location_quantity(
        warehouse_id=1,
        position_id=1,
        product_id=501,
        quantity_delta=0,
        allocated_delta=40,
        status="AVAILABLE",
    )
    atp_session.commit()

    # 3. VERIFY ATP:
    # Physical = 100
    # Allocated Loc = 40
    # Doc Reservations = 40
    # Quarantine = 0
    # ATP = 100 - max(40, 40) - 0 = 60
    # (Buggy formula would calculate: (100 - 40) - 40 = 20)
    atp = alloc_service.check_availability(warehouse_id=1, product_id=501)
    assert atp == 60, f"Expected ATP 60, but got {atp} (Double-reservation deficit occurred!)"

    # 4. Order 2 requests 30 units:
    # Under buggy formula (ATP=20), this would fail with InsufficientStockError.
    # Under correct formula (ATP=60), this must allocate successfully.
    allocations = alloc_service.allocate_fefo(
        warehouse_id=1,
        product_id=501,
        quantity=30,
        status="AVAILABLE",
    )
    assert len(allocations) >= 1
    assert sum(a["allocated_qty"] for a in allocations) == 30

    # 5. After allocating 30 units:
    # Allocated Loc = 40 + 30 = 70
    # Doc Reservations = 40
    # ATP = 100 - max(70, 40) = 30
    assert alloc_service.check_availability(warehouse_id=1, product_id=501) == 30


def test_atp_over_allocation_protection(atp_session):
    """
    Test Case 3:
    When ATP is 60 (100 physical, 40 reserved), an order requesting 65 units
    must be rejected with InsufficientStockError.
    """
    repo = InventoryRepo(atp_session)
    alloc_service = AllocationService(repo)

    # Order 1 holds 40 units
    repo.create_reservation(
        source_type="document",
        source_id=2001,
        document_id=2001,
        product_id=501,
        warehouse_id=1,
        requested_qty=40,
        created_by="SALES_AGENT",
        idempotency_key="order_2001_res",
        expires_at=None,
        status="RESERVED",
    )
    repo.adjust_location_quantity(
        warehouse_id=1,
        position_id=1,
        product_id=501,
        quantity_delta=0,
        allocated_delta=40,
        status="AVAILABLE",
    )
    atp_session.commit()

    # Attempting to allocate 65 units must fail
    with pytest.raises(InsufficientStockError) as exc_info:
        alloc_service.allocate_fefo(
            warehouse_id=1,
            product_id=501,
            quantity=65,
            status="AVAILABLE",
        )
    assert "Insufficient stock for FEFO allocation" in str(exc_info.value)


def test_atp_with_both_doc_reservation_and_soft_quarantine(atp_session):
    """
    Test Case 4:
    - 100 physical units.
    - 40 units Doc Reservation (RESERVED) + allocated at bin.
    - 15 units Soft Quarantine (PENDING_ADJUSTMENT).
    - ATP = 100 - max(40, 40) - 15 = 45 units.
    """
    repo = InventoryRepo(atp_session)
    alloc_service = AllocationService(repo)

    # 40 units reserved for sales order
    repo.create_reservation(
        source_type="document",
        source_id=3001,
        document_id=3001,
        product_id=501,
        warehouse_id=1,
        requested_qty=40,
        created_by="SALES_AGENT",
        idempotency_key="order_3001_res",
        expires_at=None,
        status="RESERVED",
    )
    repo.adjust_location_quantity(
        warehouse_id=1,
        position_id=1,
        product_id=501,
        quantity_delta=0,
        allocated_delta=40,
        status="AVAILABLE",
    )

    # 15 units soft quarantined via draft adjustment proposal
    repo.create_reservation(
        source_type="draft_proposal",
        source_id=None,
        document_id=None,
        product_id=501,
        warehouse_id=1,
        requested_qty=15,
        created_by="QA_STAFF",
        idempotency_key="soft_quarantine_PROP-TEST",
        expires_at=None,
        status="PENDING_ADJUSTMENT",
    )
    atp_session.commit()

    atp = alloc_service.check_availability(warehouse_id=1, product_id=501)
    assert atp == 45, f"Expected ATP 45, got {atp}"


def test_repo_create_reservation_eliminates_double_reservation_deficit(atp_session):
    """
    TASK-080 Acceptance Criteria:
    - Kho có 100 sản phẩm (40 sản phẩm đã reserve & allocate cho Đơn 1).
    - Đơn 2 yêu cầu 50 sản phẩm được chấp thuận thành công (thay vì bị từ chối với available=20 dưới công thức cũ).
    """
    repo = InventoryRepo(atp_session)

    # 1. Order 1 reserves 40 units and is allocated at bin
    res1_id = repo.create_reservation(
        source_type="document",
        source_id=4001,
        document_id=4001,
        product_id=501,
        warehouse_id=1,
        requested_qty=40,
        created_by="SALES_AGENT",
        idempotency_key="order_4001_res",
        expires_at=None,
        status="RESERVED",
    )
    assert res1_id > 0
    repo.adjust_location_quantity(
        warehouse_id=1,
        position_id=1,
        product_id=501,
        quantity_delta=0,
        allocated_delta=40,
        status="AVAILABLE",
    )
    atp_session.commit()

    # 2. Order 2 requests 50 units via create_reservation
    # Under old formula: available = (100 - 40) - 40 = 20 < 50 => would raise InsufficientStockError!
    # Under new ATP formula: available = 100 - max(40, 40) - 0 = 60 >= 50 => SUCCEEDS!
    res2_id = repo.create_reservation(
        source_type="document",
        source_id=4002,
        document_id=4002,
        product_id=501,
        warehouse_id=1,
        requested_qty=50,
        created_by="SALES_AGENT",
        idempotency_key="order_4002_res",
        expires_at=None,
        status="RESERVED",
    )
    assert res2_id > 0

    # 3. Order 3 requests 15 units:
    # Now valid_physical=100, doc_res=90, allocated_loc=40 => available = 100 - max(40, 90) = 10 < 15
    # Must raise InsufficientStockError!
    with pytest.raises(InsufficientStockError) as exc_info:
        repo.create_reservation(
            source_type="document",
            source_id=4003,
            document_id=4003,
            product_id=501,
            warehouse_id=1,
            requested_qty=15,
            created_by="SALES_AGENT",
            idempotency_key="order_4003_res",
            expires_at=None,
            status="RESERVED",
        )
    assert "Insufficient available stock" in str(exc_info.value)


def test_repo_create_reservation_excludes_expired_stock(atp_session):
    """
    TASK-080 Acceptance Criteria:
    - Lô hàng đã hết date không được tính vào tồn kho khả dụng để đặt trước trong create_reservation.
    """
    repo = InventoryRepo(atp_session)
    now = datetime.now(timezone.utc)

    # Seed Position 2
    pos2 = PositionModel(id=2, warehouse_id=1, code="BIN-A02", type="STORAGE", is_active=1)
    atp_session.add(pos2)
    atp_session.commit()

    # Product 502:
    # Bin 1: 50 units EXPIRED (5 days ago)
    repo.adjust_location_quantity(
        warehouse_id=1,
        position_id=1,
        product_id=502,
        quantity_delta=50,
        status="AVAILABLE",
        lot_number="LOT-EXP-PAST",
        expiry_date=now - timedelta(days=5),
    )
    # Bin 2: 30 units VALID (expiring in 30 days)
    repo.adjust_location_quantity(
        warehouse_id=1,
        position_id=2,
        product_id=502,
        quantity_delta=30,
        status="AVAILABLE",
        lot_number="LOT-VALID-FUTURE",
        expiry_date=now + timedelta(days=30),
    )
    atp_session.commit()

    # Physical total is 80 units, but only 30 units are valid and unexpired.
    # Requesting 40 units must FAIL because only 30 units are available.
    with pytest.raises(InsufficientStockError) as exc_info:
        repo.create_reservation(
            source_type="document",
            source_id=5001,
            document_id=5001,
            product_id=502,
            warehouse_id=1,
            requested_qty=40,
            created_by="SALES_AGENT",
            idempotency_key="order_5001_res",
            expires_at=None,
            status="RESERVED",
        )
    assert "Insufficient available stock" in str(exc_info.value)
    assert "Available: 30" in str(exc_info.value)

    # Requesting 25 units must SUCCEED!
    res_id = repo.create_reservation(
        source_type="document",
        source_id=5002,
        document_id=5002,
        product_id=502,
        warehouse_id=1,
        requested_qty=25,
        created_by="SALES_AGENT",
        idempotency_key="order_5002_res",
        expires_at=None,
        status="RESERVED",
    )
    assert res_id > 0
