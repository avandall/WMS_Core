"""
Unit Test Suite for Proposal Location Validation on Negative Adjustments (TASK-074 / CRIT-02).

Acceptance Criteria:
1. In InventoryService.create_draft_proposal:
   - If adjustment < 0 (or proposed_quantity < current_quantity) and neither location_code nor position_id is provided:
     Raises ValueError("location_code or position_id is required for negative inventory adjustments").
   - If adjustment < 0 and location_code is provided -> Succeeds.
   - If adjustment < 0 and position_id is provided -> Succeeds.
   - If adjustment > 0 without location -> Succeeds.
2. In API Gateway CreateProposalPayload:
   - Schema validation raises ValidationError for negative adjustment without location.
   - Schema validation passes for negative adjustment with location_code or position_id.
"""

from __future__ import annotations

import pytest
from api_gateway.schemas import CreateProposalPayload
from app.modules.inventory.application.services.inventory_service import (
    InventoryService,
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
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def service_session():
    """Isolated SQLite database setup with full schema."""
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

    # Seed position and stock
    pos = PositionModel(id=5, warehouse_id=1, code="BIN-C05", type="STORAGE", is_active=1)
    session.add(pos)

    repo = InventoryRepo(session)
    repo.adjust_location_quantity(
        warehouse_id=1,
        position_id=5,
        product_id=801,
        quantity_delta=100,
        status="AVAILABLE",
    )
    session.commit()

    yield session
    session.close()


def test_create_draft_proposal_negative_adjustment_without_location_raises_error(service_session):
    """
    1. Negative adjustment with adjustment < 0 and NO location_code or position_id
       must raise ValueError.
    """
    repo = InventoryRepo(service_session)
    service = InventoryService(repo)

    with pytest.raises(ValueError) as exc_info:
        service.create_draft_proposal(
            proposal_id="PROP-FAIL-01",
            sku_code="801",
            warehouse_id=1,
            adjustment=-20,
            reason="Damaged stock write-off",
            requested_by="QA_STAFF",
        )
    assert "location_code or position_id is required for negative inventory adjustments" in str(exc_info.value)


def test_create_draft_proposal_proposed_less_than_current_without_location_raises_error(service_session):
    """
    2. Negative adjustment calculated via proposed_quantity < current_quantity
       without location_code or position_id must raise ValueError.
    """
    repo = InventoryRepo(service_session)
    service = InventoryService(repo)

    with pytest.raises(ValueError) as exc_info:
        service.create_draft_proposal(
            proposal_id="PROP-FAIL-02",
            sku_code="801",
            warehouse_id=1,
            current_quantity=100,
            proposed_quantity=80,
            reason="Shrinkage detected",
            requested_by="STAFF",
        )
    assert "location_code or position_id is required for negative inventory adjustments" in str(exc_info.value)


def test_create_draft_proposal_negative_adjustment_with_location_code_succeeds(service_session):
    """
    3. Negative adjustment with location_code succeeds and saves proposal.
    """
    repo = InventoryRepo(service_session)
    service = InventoryService(repo)

    proposal = service.create_draft_proposal(
        proposal_id="PROP-SUCCESS-01",
        sku_code="801",
        warehouse_id=1,
        location_code="BIN-C05",
        adjustment=-15,
        reason="Defective batch disposal",
        requested_by="QA_STAFF",
    )
    assert proposal.proposal_id == "PROP-SUCCESS-01"
    assert proposal.location_code == "BIN-C05"
    assert proposal.adjustment == -15


def test_create_draft_proposal_negative_adjustment_with_position_id_succeeds(service_session):
    """
    4. Negative adjustment with position_id succeeds and saves proposal.
    """
    repo = InventoryRepo(service_session)
    service = InventoryService(repo)

    proposal = service.create_draft_proposal(
        proposal_id="PROP-SUCCESS-02",
        sku_code="801",
        warehouse_id=1,
        position_id=5,
        adjustment=-10,
        reason="Disposed 10 expired items",
        requested_by="WAREHOUSE_STAFF",
    )
    assert proposal.proposal_id == "PROP-SUCCESS-02"
    assert proposal.position_id == 5
    assert proposal.adjustment == -10


def test_create_draft_proposal_positive_adjustment_without_location_succeeds(service_session):
    """
    5. Positive adjustment without location is allowed (e.g. general inbound adjustment).
    """
    repo = InventoryRepo(service_session)
    service = InventoryService(repo)

    proposal = service.create_draft_proposal(
        proposal_id="PROP-POS-01",
        sku_code="801",
        warehouse_id=1,
        adjustment=25,
        reason="Found extra unallocated stock",
        requested_by="OPERATOR",
    )
    assert proposal.proposal_id == "PROP-POS-01"
    assert proposal.adjustment == 25


def test_api_gateway_schema_rejects_negative_adjustment_without_location():
    """
    6. API Gateway CreateProposalPayload raises ValidationError when adjustment < 0 without location.
    """
    with pytest.raises(ValidationError) as exc_info:
        CreateProposalPayload(
            sku_code="801",
            warehouse_id=1,
            adjustment=-30,
            reason="Write-off without location",
        )
    assert "location_code or position_id is required for negative inventory adjustments" in str(exc_info.value)


def test_api_gateway_schema_accepts_negative_adjustment_with_location():
    """
    7. API Gateway CreateProposalPayload validates successfully when location is provided.
    """
    payload = CreateProposalPayload(
        sku_code="801",
        warehouse_id=1,
        location_code="BIN-C05",
        adjustment=-30,
        reason="Write-off with bin location",
    )
    assert payload.adjustment == -30
    assert payload.location_code == "BIN-C05"
