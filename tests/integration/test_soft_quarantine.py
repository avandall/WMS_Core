"""
Integration Test Suite for Soft Quarantine Mechanism on Negative Draft Proposals (TASK-064 / CRIT-03).

Acceptance Criteria:
1. When DraftAdjustmentProposal has adjustment < 0:
   - Automatically generates StockReservation with status="PENDING_ADJUSTMENT" and requested_qty=abs(adjustment).
2. ATP and AllocationService.check_availability():
   - Automatically deducts all stock held under status="PENDING_ADJUSTMENT".
3. Over-allocation / Race Condition Protection:
   - Orders attempting to allocate more than the remaining available stock fail with InsufficientStockError.
4. Approval Transition:
   - When proposal is approved, reservation transitions to CONSUMED and physical stock decreases.
5. Rejection Transition:
   - When proposal is rejected, reservation transitions to RELEASED and stock is restored to AVAILABLE.
"""

from __future__ import annotations

from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.shared.core.database import Base
from app.shared.domain.business_exceptions import InsufficientStockError
from app.modules.inventory.infrastructure.models.draft_proposal import DraftProposalModel
from app.modules.inventory.infrastructure.models.warehouse_inventory import WarehouseInventoryModel
from app.modules.inventory.infrastructure.models.inventory_location import InventoryLocationModel
from app.modules.inventory.infrastructure.models.position import PositionModel
from app.modules.inventory.infrastructure.models.stock_reservation import StockReservationModel
from app.modules.inventory.infrastructure.models.inventory_transaction import InventoryTransactionModel
from app.modules.inventory.infrastructure.models.movement_ledger import InventoryMovementLedgerModel
from app.modules.inventory.infrastructure.repositories.inventory_repo import InventoryRepo
from app.modules.inventory.application.services.inventory_service import InventoryService
from app.modules.inventory.application.services.allocation_service import AllocationService


@pytest.fixture
def soft_quarantine_session():
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
    pos = PositionModel(id=10, warehouse_id=1, code="BIN-A1", type="STORAGE", is_active=1)
    session.add(pos)
    session.commit()

    # Seed stock: 100 units of SKU 301 at Warehouse 1, Position 10
    repo = InventoryRepo(session)
    repo.adjust_location_quantity(
        warehouse_id=1,
        position_id=10,
        product_id=301,
        quantity_delta=100,
        status="AVAILABLE",
    )
    session.commit()

    yield session
    session.close()


def test_negative_proposal_creates_soft_quarantine_reservation(soft_quarantine_session):
    """
    1. Creating a negative draft adjustment (-30) automatically creates
       a StockReservation with status='PENDING_ADJUSTMENT'.
    2. ATP drops from 100 to 70.
    """
    repo = InventoryRepo(soft_quarantine_session)
    service = InventoryService(repo)
    alloc_service = AllocationService(repo)

    # Initial ATP must be 100
    assert alloc_service.check_availability(warehouse_id=1, product_id=301) == 100

    # Create proposal proposing decrease from 100 to 70 (adj = -30)
    proposal = service.create_draft_proposal(
        proposal_id="PROP-QUARANTINE-01",
        sku_code="301",
        warehouse_id=1,
        current_quantity=100,
        proposed_quantity=70,
        adjustment=-30,
        reason="Detected water damage in 30 units",
        requested_by="QA_INSPECTOR",
    )

    # 1. Verify reservation created with status='PENDING_ADJUSTMENT'
    res = soft_quarantine_session.execute(
        select(StockReservationModel).where(
            StockReservationModel.idempotency_key == "soft_quarantine_PROP-QUARANTINE-01"
        )
    ).scalar_one_or_none()

    assert res is not None
    assert res.status == "PENDING_ADJUSTMENT"
    assert res.product_id == 301
    assert res.warehouse_id == 1
    assert res.reserved_qty == 30
    assert res.requested_qty == 30

    # 2. Verify ATP is now 70 (100 physical - 30 pending adjustment)
    atp = alloc_service.check_availability(warehouse_id=1, product_id=301)
    assert atp == 70, f"Expected ATP 70, got {atp}"


def test_soft_quarantine_blocks_over_allocation_race_condition(soft_quarantine_session):
    """
    Race Condition Prevention:
    When 30 units are pending write-off, a new sales order cannot allocate
    more than 70 units (e.g. 80 units must raise InsufficientStockError).
    """
    repo = InventoryRepo(soft_quarantine_session)
    service = InventoryService(repo)
    alloc_service = AllocationService(repo)

    service.create_draft_proposal(
        proposal_id="PROP-QUARANTINE-02",
        sku_code="301",
        warehouse_id=1,
        adjustment=-30,
        reason="Quality defect write-off proposal",
        requested_by="AI_AGENT",
    )

    # Attempting to allocate 80 units must fail because ATP is 70
    with pytest.raises(InsufficientStockError) as exc_info:
        alloc_service.allocate_fefo(
            warehouse_id=1,
            product_id=301,
            quantity=80,
            status="AVAILABLE",
        )
    assert "Insufficient stock for FEFO allocation" in str(exc_info.value)

    # Allocating 70 units (the exact available ATP) must succeed
    allocations = alloc_service.allocate_fefo(
        warehouse_id=1,
        product_id=301,
        quantity=70,
        status="AVAILABLE",
    )
    assert len(allocations) >= 1
    assert sum(a["allocated_qty"] for a in allocations) == 70


def test_soft_quarantine_consumed_on_proposal_approval(soft_quarantine_session):
    """
    When proposal is APPROVED:
    1. Reservation transitions to CONSUMED.
    2. Physical stock drops from 100 to 70.
    3. Active reservations drop to 0.
    """
    repo = InventoryRepo(soft_quarantine_session)
    service = InventoryService(repo)
    alloc_service = AllocationService(repo)

    service.create_draft_proposal(
        proposal_id="PROP-QUARANTINE-03",
        sku_code="301",
        warehouse_id=1,
        location_code="BIN-A1",
        position_id=10,
        current_quantity=100,
        proposed_quantity=70,
        adjustment=-30,
        reason="Approved scrap of expired goods",
        requested_by="WAREHOUSE_STAFF",
    )

    # Manager approves proposal
    executed, tx_id = service.approve_draft_proposal(
        proposal_id="PROP-QUARANTINE-03",
        approved_by="MANAGER_LISA",
    )
    assert executed.status == "EXECUTED"

    # Verify reservation is CONSUMED
    res = soft_quarantine_session.execute(
        select(StockReservationModel).where(
            StockReservationModel.idempotency_key == "soft_quarantine_PROP-QUARANTINE-03"
        )
    ).scalar_one_or_none()
    assert res.status == "CONSUMED"
    assert res.consumed_qty == 30
    assert res.reserved_qty == 0

    # Verify physical stock is now 70
    assert service.get_quantity(301, warehouse_id=1) == 70
    loc_stock = repo.get_inventory_locations(warehouse_id=1, product_id=301)
    assert loc_stock[0]["quantity"] == 70

    # Verify ATP is 70
    assert alloc_service.check_availability(warehouse_id=1, product_id=301) == 70


def test_soft_quarantine_released_on_proposal_rejection(soft_quarantine_session):
    """
    When proposal is REJECTED:
    1. Reservation transitions to RELEASED.
    2. Physical stock remains 100.
    3. ATP is restored back to 100.
    4. An order of 90 units can now be allocated.
    """
    repo = InventoryRepo(soft_quarantine_session)
    service = InventoryService(repo)
    alloc_service = AllocationService(repo)

    service.create_draft_proposal(
        proposal_id="PROP-QUARANTINE-04",
        sku_code="301",
        warehouse_id=1,
        current_quantity=100,
        proposed_quantity=70,
        adjustment=-30,
        reason="False alarm water damage",
        requested_by="OPERATOR",
    )

    # While pending: ATP is 70
    assert alloc_service.check_availability(warehouse_id=1, product_id=301) == 70

    # Manager rejects proposal
    rejected = service.reject_draft_proposal(
        proposal_id="PROP-QUARANTINE-04",
        rejected_by="MANAGER_LISA",
        rejection_reason="Items re-inspected and confirmed undamaged",
    )
    assert rejected.status == "REJECTED"

    # Verify reservation is RELEASED
    res = soft_quarantine_session.execute(
        select(StockReservationModel).where(
            StockReservationModel.idempotency_key == "soft_quarantine_PROP-QUARANTINE-04"
        )
    ).scalar_one_or_none()
    assert res.status == "RELEASED"
    assert res.reserved_qty == 0

    # Verify physical stock remains 100
    assert service.get_quantity(301, warehouse_id=1) == 100

    # Verify ATP is fully restored to 100
    assert alloc_service.check_availability(warehouse_id=1, product_id=301) == 100

    # Order of 90 units now succeeds!
    allocations = alloc_service.allocate_fefo(
        warehouse_id=1,
        product_id=301,
        quantity=90,
        status="AVAILABLE",
    )
    assert sum(a["allocated_qty"] for a in allocations) == 90
