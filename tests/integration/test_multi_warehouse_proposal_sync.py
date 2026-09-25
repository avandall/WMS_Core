"""
Integration Test for Multi-Warehouse & Location Ledger Synchronization (TASK-063 / CRIT-01 & CRIT-02).

Acceptance Criteria:
1. DraftProposalModel stores warehouse_id, location_code, position_id.
2. Approval does NOT hardcode warehouse_id=1; uses proposal.warehouse_id.
3. Dual Ledger Synchronization:
   - When proposal with location_code is approved, updates both `inventory_locations`
     and aggregate `warehouse_inventory` at the target warehouse.
   - Other warehouses (e.g. warehouse_id=1) remain completely untouched.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.shared.core.database import Base
from app.modules.inventory.infrastructure.models.draft_proposal import DraftProposalModel
from app.modules.inventory.infrastructure.models.warehouse_inventory import WarehouseInventoryModel
from app.modules.inventory.infrastructure.models.inventory_location import InventoryLocationModel
from app.modules.inventory.infrastructure.models.position import PositionModel
from app.modules.inventory.infrastructure.models.stock_reservation import StockReservationModel
from app.modules.inventory.infrastructure.models.inventory_transaction import InventoryTransactionModel
from app.modules.inventory.infrastructure.models.movement_ledger import InventoryMovementLedgerModel
from app.modules.inventory.infrastructure.repositories.inventory_repo import InventoryRepo
from app.modules.inventory.application.services.inventory_service import InventoryService


@pytest.fixture
def multi_wh_session():
    """Isolated SQLite in-memory DB with all required inventory & location tables."""
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

    # Seed positions
    pos1 = PositionModel(id=1, warehouse_id=1, code="LOC-01", type="STORAGE", is_active=1)
    pos2 = PositionModel(id=2, warehouse_id=2, code="LOC-02", type="STORAGE", is_active=1)
    session.add_all([pos1, pos2])
    session.commit()

    # Seed stock via repo to initialize both inventory_locations and warehouse_inventory summaries
    repo = InventoryRepo(session)
    # Warehouse 1: 100 units of SKU 201 at Position 1 (LOC-01)
    repo.adjust_location_quantity(
        warehouse_id=1,
        position_id=1,
        product_id=201,
        quantity_delta=100,
        status="AVAILABLE",
    )
    # Warehouse 2: 50 units of SKU 201 at Position 2 (LOC-02)
    repo.adjust_location_quantity(
        warehouse_id=2,
        position_id=2,
        product_id=201,
        quantity_delta=50,
        status="AVAILABLE",
    )
    session.commit()

    yield session
    session.close()


def test_multi_warehouse_proposal_approval_dual_ledger_sync(multi_wh_session):
    """
    TASK-063 Verification:
    Proposal created for Warehouse 2, Location 'LOC-02', adjustment -10:
    1. Warehouse 2 location stock (inventory_locations) drops from 50 to 40.
    2. Warehouse 2 total summary (warehouse_inventory) drops from 50 to 40.
    3. Warehouse 1 stock remains strictly 100 in both tables.
    """
    repo = InventoryRepo(multi_wh_session)
    service = InventoryService(repo)

    # 1. Verify baseline in both warehouses
    wh1_locs = repo.get_inventory_locations(warehouse_id=1, product_id=201)
    assert len(wh1_locs) == 1
    assert wh1_locs[0]["quantity"] == 100
    assert service.get_quantity(201, warehouse_id=1) == 100

    wh2_locs = repo.get_inventory_locations(warehouse_id=2, product_id=201)
    assert len(wh2_locs) == 1
    assert wh2_locs[0]["quantity"] == 50
    assert service.get_quantity(201, warehouse_id=2) == 50

    # 2. Create proposal for Warehouse 2, Location 'LOC-02'
    proposal = DraftProposalModel(
        proposal_id="PROP-WH2-SYNC-01",
        proposal_type="DraftAdjustmentProposal",
        sku_code="201",
        warehouse_id=2,
        location_code="LOC-02",
        position_id=2,
        current_quantity=50,
        proposed_quantity=40,
        adjustment=-10,
        reason="Physical audit defect deduction at WH2",
        requested_by="AUDITOR_WH2",
        status="DRAFT_PROPOSAL",
    )
    repo.save_draft_proposal(proposal)

    # Verify attributes stored on proposal model
    saved_prop = repo.get_draft_proposal("PROP-WH2-SYNC-01")
    assert saved_prop.warehouse_id == 2
    assert saved_prop.location_code == "LOC-02"
    assert saved_prop.position_id == 2

    # 3. Manager approves proposal
    executed, tx_id = service.approve_draft_proposal(
        proposal_id="PROP-WH2-SYNC-01",
        approved_by="MANAGER_WH2",
    )
    assert executed.status == "EXECUTED"

    # 4. Verify Warehouse 2: Dual ledger is synchronized to 40
    wh2_locs_after = repo.get_inventory_locations(warehouse_id=2, product_id=201)
    assert len(wh2_locs_after) == 1
    assert wh2_locs_after[0]["quantity"] == 40, "Location stock must be reduced to 40"
    wh2_total = service.get_quantity(201, warehouse_id=2)
    assert wh2_total == 40, "Warehouse 2 total stock must be reduced to 40"

    # 5. Verify Warehouse 1: Completely unaffected
    wh1_locs_after = repo.get_inventory_locations(warehouse_id=1, product_id=201)
    assert len(wh1_locs_after) == 1
    assert wh1_locs_after[0]["quantity"] == 100, "Warehouse 1 location stock must NOT be modified"
    wh1_total = service.get_quantity(201, warehouse_id=1)
    assert wh1_total == 100, "Warehouse 1 total stock must NOT be modified"


def test_positive_proposal_multi_warehouse_dual_ledger_sync(multi_wh_session):
    """
    Positive adjustment (+15) at Warehouse 2, Location 'LOC-02':
    1. Warehouse 2 location stock increases from 50 to 65.
    2. Warehouse 2 total summary increases from 50 to 65.
    3. Warehouse 1 remains strictly 100.
    """
    repo = InventoryRepo(multi_wh_session)
    service = InventoryService(repo)

    proposal = DraftProposalModel(
        proposal_id="PROP-WH2-POS-02",
        proposal_type="DraftAdjustmentProposal",
        sku_code="201",
        warehouse_id=2,
        location_code="LOC-02",
        position_id=2,
        current_quantity=50,
        proposed_quantity=65,
        adjustment=15,
        reason="Found extra stock during cycle count",
        requested_by="AI_AGENT",
        status="DRAFT_PROPOSAL",
    )
    repo.save_draft_proposal(proposal)

    service.approve_draft_proposal(
        proposal_id="PROP-WH2-POS-02",
        approved_by="MANAGER_WH2",
    )

    # Warehouse 2 updated
    assert service.get_quantity(201, warehouse_id=2) == 65
    locs = repo.get_inventory_locations(warehouse_id=2, product_id=201)
    assert locs[0]["quantity"] == 65

    # Warehouse 1 untouched
    assert service.get_quantity(201, warehouse_id=1) == 100
    locs1 = repo.get_inventory_locations(warehouse_id=1, product_id=201)
    assert locs1[0]["quantity"] == 100
