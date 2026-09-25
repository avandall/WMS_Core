"""
Integration Test Suite for CreateDraftProposal RPC & POST /api/v1/proposals Endpoint (TASK-073 / CRIT-05).

Acceptance Criteria:
1. inventory.proto contains CreateDraftProposal RPC with Request and Response schemas.
2. InventoryServiceServicer implements CreateDraftProposal:
   - Successfully creates a draft proposal in DRAFT_PROPOSAL status.
   - Automatically handles soft quarantine reservation when adjustment < 0.
   - Returns structured DraftProposalRow.
3. API Gateway route POST /api/v1/proposals:
   - Validates CreateProposalPayload schema.
   - Authenticated user calls POST /api/v1/proposals -> returns HTTP 201 Created.
   - Response contains created proposal details.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from api_gateway.app import create_app
from api_gateway.auth import CurrentUser, get_current_user
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
from fastapi.testclient import TestClient
from inventory_service.gen.wms.inventory.v1 import inventory_pb2
from inventory_service.grpc_servicer import InventoryServiceServicer
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def proposal_session():
    """Isolated SQLite database setup with full inventory and proposal tables."""
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
    pos = PositionModel(id=1, warehouse_id=1, code="BIN-B01", type="STORAGE", is_active=1)
    session.add(pos)

    # Seed baseline inventory
    repo = InventoryRepo(session)
    repo.adjust_location_quantity(
        warehouse_id=1,
        position_id=1,
        product_id=701,
        quantity_delta=100,
        status="AVAILABLE",
    )
    session.commit()

    yield session
    session.close()


def test_grpc_create_draft_proposal_positive_adjustment(proposal_session):
    """
    Test direct gRPC call to CreateDraftProposal with positive adjustment (+20 units).
    """
    servicer = InventoryServiceServicer()

    with patch("inventory_service.grpc_servicer.get_db_session") as mock_db:
        mock_db.return_value.__enter__.return_value = proposal_session
        mock_db.return_value.__exit__.return_value = None

        req = inventory_pb2.CreateDraftProposalRequest(
            proposal_id="PROP-CREATE-001",
            proposal_type="DraftAdjustmentProposal",
            sku_code="701",
            warehouse_id=1,
            location_code="BIN-B01",
            position_id=1,
            current_quantity=100,
            proposed_quantity=120,
            adjustment=20,
            reason="Found extra units during morning audit",
            requested_by="AUDITOR_BOB",
        )

        resp = servicer.CreateDraftProposal(req, None)
        assert resp.success is True
        assert resp.message == "Draft proposal created successfully"
        assert resp.proposal.proposal_id == "PROP-CREATE-001"
        assert resp.proposal.status == "DRAFT_PROPOSAL"
        assert resp.proposal.adjustment == 20
        assert resp.proposal.requested_by == "AUDITOR_BOB"
        assert resp.proposal.warehouse_id == 1
        assert resp.proposal.location_code == "BIN-B01"

    # Verify persisted in DB
    saved = proposal_session.execute(
        select(DraftProposalModel).where(DraftProposalModel.proposal_id == "PROP-CREATE-001")
    ).scalar_one_or_none()
    assert saved is not None
    assert saved.status == "DRAFT_PROPOSAL"
    assert saved.adjustment == 20


def test_grpc_create_draft_proposal_negative_with_soft_quarantine(proposal_session):
    """
    Test direct gRPC call to CreateDraftProposal with negative adjustment (-25 units).
    Must automatically trigger soft quarantine reservation (PENDING_ADJUSTMENT).
    """
    servicer = InventoryServiceServicer()

    with patch("inventory_service.grpc_servicer.get_db_session") as mock_db:
        mock_db.return_value.__enter__.return_value = proposal_session
        mock_db.return_value.__exit__.return_value = None

        req = inventory_pb2.CreateDraftProposalRequest(
            proposal_id="PROP-CREATE-002",
            proposal_type="DraftAdjustmentProposal",
            sku_code="701",
            warehouse_id=1,
            location_code="BIN-B01",
            position_id=1,
            current_quantity=100,
            proposed_quantity=75,
            adjustment=-25,
            reason="Damaged items write-off",
            requested_by="OPERATOR_ALICE",
        )

        resp = servicer.CreateDraftProposal(req, None)
        assert resp.success is True
        assert resp.proposal.proposal_id == "PROP-CREATE-002"
        assert resp.proposal.adjustment == -25

    # Verify soft quarantine reservation created
    res = proposal_session.execute(
        select(StockReservationModel).where(
            StockReservationModel.idempotency_key == "soft_quarantine_PROP-CREATE-002"
        )
    ).scalar_one_or_none()
    assert res is not None
    assert res.status == "PENDING_ADJUSTMENT"
    assert res.reserved_qty == 25


def test_api_gateway_post_proposal_creates_proposal_201():
    """
    Test API Gateway REST endpoint POST /api/v1/proposals:
    - Authenticated user calls endpoint with CreateProposalPayload.
    - Receives HTTP 201 Created and response containing proposal details.
    """
    app = create_app()
    client = TestClient(app)

    auth_user = CurrentUser(user_id=101, role="warehouse_staff", email="staff@wms.com")
    app.dependency_overrides[get_current_user] = lambda: auth_user

    mock_row = inventory_pb2.DraftProposalRow(
        proposal_id="PROP-REST-001",
        proposal_type="DraftAdjustmentProposal",
        sku_code="701",
        current_quantity=100,
        proposed_quantity=110,
        adjustment=10,
        reason="Periodic spot-check discrepancy",
        requested_by="101",
        status="DRAFT_PROPOSAL",
        warehouse_id=1,
        location_code="BIN-B01",
        position_id=1,
    )

    mock_grpc_resp = inventory_pb2.CreateDraftProposalResponse(
        success=True,
        message="Draft proposal created successfully",
        proposal=mock_row,
    )

    with patch("api_gateway.routes.inventory_stub") as mock_stub_factory:
        mock_stub = MagicMock()
        mock_stub_factory.return_value.__enter__.return_value = mock_stub
        mock_stub.CreateDraftProposal.return_value = mock_grpc_resp

        payload = {
            "proposal_id": "PROP-REST-001",
            "proposal_type": "DraftAdjustmentProposal",
            "sku_code": "701",
            "warehouse_id": 1,
            "location_code": "BIN-B01",
            "position_id": 1,
            "current_quantity": 100,
            "proposed_quantity": 110,
            "adjustment": 10,
            "reason": "Periodic spot-check discrepancy",
        }

        resp = client.post("/api/v1/proposals", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["success"] is True
        assert data["message"] == "Draft proposal created successfully"
        assert data["proposal"]["proposal_id"] == "PROP-REST-001"
        assert data["proposal"]["status"] == "DRAFT_PROPOSAL"
        assert data["proposal"]["adjustment"] == 10

        # Verify gRPC was called with requested_by set from CurrentUser
        mock_stub.CreateDraftProposal.assert_called_once()
        call_arg = mock_stub.CreateDraftProposal.call_args[0][0]
        assert call_arg.requested_by == "101"
        assert call_arg.sku_code == "701"

    app.dependency_overrides.clear()
