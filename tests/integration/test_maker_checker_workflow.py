"""
Integration & E2E Test Suite for Maker-Checker Workflow (TASK-059 / CRIT-09).

Acceptance Criteria:
1. AI Agent creates draft proposal (status = 'DRAFT_PROPOSAL') -> Physical warehouse inventory is unchanged.
2. Warehouse Manager approves proposal -> System triggers ConfirmInventoryTransaction:
   - Physical inventory adjusts positively (ADJUSTMENT_IN) or negatively (ADJUSTMENT_OUT).
   - Inventory transaction ledger records the event.
   - Proposal status transitions to 'EXECUTED' with approved_by, approved_at, executed_at, executed_by.
3. Warehouse Manager rejects proposal -> Rejection reason recorded, stock unchanged, status is 'REJECTED'.
4. State machine locks terminal states (REJECTED and EXECUTED cannot transition back).
5. API Gateway REST endpoints:
   - GET /api/v1/proposals
   - POST /api/v1/proposals/{id}/approve (403 for unauthorized, 200 for manager)
   - POST /api/v1/proposals/{id}/reject (403 for unauthorized, 200 for manager)
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.shared.core.database import Base
from app.modules.inventory.infrastructure.models.draft_proposal import DraftProposalModel
from app.modules.inventory.infrastructure.models.warehouse_inventory import WarehouseInventoryModel
from app.modules.inventory.infrastructure.models.inventory_transaction import InventoryTransactionModel
from app.modules.inventory.infrastructure.models.movement_ledger import InventoryMovementLedgerModel
from app.modules.inventory.infrastructure.repositories.inventory_repo import InventoryRepo
from app.modules.inventory.application.services.inventory_service import InventoryService
from inventory_service.grpc_servicer import InventoryServiceServicer
from inventory_service.gen.wms.inventory.v1 import inventory_pb2
from api_gateway.app import create_app
from api_gateway.auth import CurrentUser, get_current_user


@pytest.fixture
def db_session():
    """Isolated SQLite in-memory database with inventory and draft proposal tables."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        bind=engine,
        tables=[
            WarehouseInventoryModel.__table__,
            DraftProposalModel.__table__,
            InventoryTransactionModel.__table__,
            InventoryMovementLedgerModel.__table__,
        ],
    )
    Session = sessionmaker(bind=engine)
    session = Session()

    # Seed baseline inventory for product 101 with initial 50 units
    inv = WarehouseInventoryModel(
        product_id=101,
        warehouse_id=1,
        quantity=50,
        physical_qty=50,
        reserved_qty=0,
        incoming_qty=0,
        in_transit_qty=0,
    )
    session.add(inv)
    session.commit()

    yield session
    session.close()


def test_ai_draft_proposal_creation_does_not_mutate_physical_inventory(db_session):
    """
    Step 1: AI Agent generates a DraftAdjustmentProposal.
    Verify that physical warehouse inventory remains strictly unmodified.
    """
    repo = InventoryRepo(db_session)
    service = InventoryService(repo)

    # Simulate AI Agent creating a draft adjustment proposal
    proposal = DraftProposalModel(
        proposal_id="PROP-AI-001",
        proposal_type="DraftAdjustmentProposal",
        sku_code="101",
        current_quantity=50,
        proposed_quantity=75,
        adjustment=25,
        reason="AI Cycle Count Discrepancy Detected",
        requested_by="AI_AGENT_CYCLE_COUNT",
        status="DRAFT_PROPOSAL",
    )
    repo.save_draft_proposal(proposal)

    # Verify proposal is saved as DRAFT_PROPOSAL
    saved = repo.get_draft_proposal("PROP-AI-001")
    assert saved is not None
    assert saved.status == "DRAFT_PROPOSAL"
    assert saved.approved_by is None
    assert saved.executed_at is None

    # CRITICAL: Physical stock MUST remain at 50
    curr_qty = service.get_total_quantity(101)
    assert curr_qty == 50, "Physical stock must NOT change when proposal is only in DRAFT state"


def test_manager_approval_triggers_execution_and_updates_stock_positive(db_session):
    """
    Step 2: Warehouse Manager approves a positive adjustment (+25).
    Verify that inventory increases to 75, status becomes EXECUTED, and transaction is logged.
    """
    repo = InventoryRepo(db_session)
    mock_publisher = MagicMock()
    service = InventoryService(repo, event_publisher=mock_publisher)

    proposal = DraftProposalModel(
        proposal_id="PROP-POS-002",
        proposal_type="DraftAdjustmentProposal",
        sku_code="101",
        current_quantity=50,
        proposed_quantity=75,
        adjustment=25,
        reason="Stock found during physical audit",
        requested_by="AI_AGENT",
        status="DRAFT_PROPOSAL",
    )
    repo.save_draft_proposal(proposal)

    # Manager approves proposal
    executed_proposal, tx_id = service.approve_draft_proposal(
        proposal_id="PROP-POS-002",
        approved_by="WM_MANAGER_JOHN",
        digital_signature="SIG-ED25519-ABCD-1234",
    )

    # Verify proposal state
    assert executed_proposal.status == "EXECUTED"
    assert executed_proposal.approved_by == "WM_MANAGER_JOHN"
    assert executed_proposal.approved_at is not None
    assert executed_proposal.executed_by == "WM_MANAGER_JOHN"
    assert executed_proposal.executed_at is not None
    assert executed_proposal.digital_signature == "SIG-ED25519-ABCD-1234"

    # Verify physical stock changed from 50 to 75
    new_qty = service.get_total_quantity(101)
    assert new_qty == 75, f"Expected inventory to be 75, got {new_qty}"

    # Verify transaction ledger has an entry for ADJUSTMENT_IN
    txs = repo.list_transactions(product_id=101, transaction_type="ADJUSTMENT_IN")
    assert len(txs) >= 1
    assert txs[0]["quantity"] == 25

    # Verify event published
    mock_publisher.publish.assert_any_call(
        event_type="InventoryAdjusted",
        payload=mock_publisher.publish.call_args[1]["payload"],
    )


def test_manager_approval_triggers_execution_and_updates_stock_negative(db_session):
    """
    Step 3: Warehouse Manager approves a negative adjustment (-20).
    Verify that inventory decreases from 50 to 30 with ADJUSTMENT_OUT transaction.
    """
    repo = InventoryRepo(db_session)
    service = InventoryService(repo)

    proposal = DraftProposalModel(
        proposal_id="PROP-NEG-003",
        proposal_type="DraftAdjustmentProposal",
        sku_code="101",
        current_quantity=50,
        proposed_quantity=30,
        adjustment=-20,
        reason="Damaged goods written off",
        requested_by="AI_AGENT",
        status="DRAFT_PROPOSAL",
    )
    repo.save_draft_proposal(proposal)

    executed_proposal, tx_id = service.approve_draft_proposal(
        proposal_id="PROP-NEG-003",
        approved_by="WM_MANAGER_ALICE",
    )

    assert executed_proposal.status == "EXECUTED"
    assert executed_proposal.approved_by == "WM_MANAGER_ALICE"
    assert executed_proposal.executed_at is not None

    # Stock decreased from 50 to 30
    assert service.get_total_quantity(101) == 30

    txs = repo.list_transactions(product_id=101, transaction_type="ADJUSTMENT_OUT")
    assert len(txs) >= 1
    assert txs[0]["quantity"] == 20


def test_manager_rejection_leaves_stock_unchanged_and_sets_reason(db_session):
    """
    Step 4: Warehouse Manager rejects the proposal with a reason.
    Verify status becomes REJECTED and physical stock is untouched.
    """
    repo = InventoryRepo(db_session)
    service = InventoryService(repo)

    proposal = DraftProposalModel(
        proposal_id="PROP-REJ-004",
        proposal_type="DraftAdjustmentProposal",
        sku_code="101",
        current_quantity=50,
        proposed_quantity=10,
        adjustment=-40,
        reason="Suspected theft",
        requested_by="AI_AGENT",
        status="DRAFT_PROPOSAL",
    )
    repo.save_draft_proposal(proposal)

    rejected_proposal = service.reject_draft_proposal(
        proposal_id="PROP-REJ-004",
        rejected_by="WM_MANAGER_BOB",
        rejection_reason="Investigation required before writing off stock",
    )

    assert rejected_proposal.status == "REJECTED"
    assert rejected_proposal.approved_by == "WM_MANAGER_BOB"
    assert rejected_proposal.rejection_reason == "Investigation required before writing off stock"
    assert rejected_proposal.executed_at is None

    # Stock is unchanged
    assert service.get_total_quantity(101) == 50


def test_terminal_states_cannot_transition_or_re_execute(db_session):
    """
    Step 5: Ensure strict state machine protection.
    A rejected or executed proposal cannot be approved again.
    """
    repo = InventoryRepo(db_session)
    service = InventoryService(repo)

    # 1. Rejected proposal cannot be approved
    p1 = DraftProposalModel(
        proposal_id="PROP-LOCK-001",
        proposal_type="DraftAdjustmentProposal",
        sku_code="101",
        current_quantity=50,
        proposed_quantity=60,
        adjustment=10,
        status="REJECTED",
        rejection_reason="Invalid audit",
    )
    repo.save_draft_proposal(p1)

    with pytest.raises(ValueError, match="cannot be approved in state REJECTED"):
        service.approve_draft_proposal("PROP-LOCK-001", approved_by="WM_MANAGER")

    # 2. Executed proposal cannot be rejected, but approval is idempotent (TASK-070)
    p2 = DraftProposalModel(
        proposal_id="PROP-LOCK-002",
        proposal_type="DraftAdjustmentProposal",
        sku_code="101",
        current_quantity=50,
        proposed_quantity=60,
        adjustment=10,
        status="EXECUTED",
        approved_by="WM_MANAGER",
        executed_by="WM_MANAGER",
    )
    repo.save_draft_proposal(p2)

    # Idempotent approval must succeed with 0 stock delta instead of raising ValueError
    executed_proposal, delta = service.approve_draft_proposal("PROP-LOCK-002", approved_by="WM_MANAGER")
    assert executed_proposal.status == "EXECUTED"
    assert delta == 0

    with pytest.raises(ValueError, match="cannot be rejected in state EXECUTED"):
        service.reject_draft_proposal("PROP-LOCK-002", rejected_by="WM_MANAGER", rejection_reason="Too late")


def test_grpc_servicer_draft_proposals_lifecycle(db_session):
    """
    Step 6: Test gRPC servicer layer directly for List, Approve, Reject.
    """
    servicer = InventoryServiceServicer()

    # Patch get_db_session in servicer to use our test db_session
    from contextlib import contextmanager

    @contextmanager
    def mock_db():
        yield db_session

    with patch("inventory_service.grpc_servicer.get_db_session", mock_db):
        repo = InventoryRepo(db_session)
        prop = DraftProposalModel(
            proposal_id="GRPC-PROP-100",
            proposal_type="DraftAdjustmentProposal",
            sku_code="101",
            current_quantity=50,
            proposed_quantity=65,
            adjustment=15,
            reason="gRPC Test Proposal",
            requested_by="AI_SYSTEM",
            status="DRAFT_PROPOSAL",
        )
        repo.save_draft_proposal(prop)

        # 1. ListDraftProposals
        list_req = inventory_pb2.ListDraftProposalsRequest(status="DRAFT_PROPOSAL")
        list_resp = servicer.ListDraftProposals(list_req, None)
        assert list_resp.total >= 1
        found = [p for p in list_resp.proposals if p.proposal_id == "GRPC-PROP-100"]
        assert len(found) == 1
        assert found[0].adjustment == 15

        # 2. ApproveDraftProposal
        app_req = inventory_pb2.ApproveDraftProposalRequest(
            proposal_id="GRPC-PROP-100",
            approved_by="GRPC_MANAGER",
            digital_signature="SIG-GRPC",
        )
        app_resp = servicer.ApproveDraftProposal(app_req, None)
        assert app_resp.success is True
        assert app_resp.proposal.status == "EXECUTED"
        assert app_resp.proposal.approved_by == "GRPC_MANAGER"


def test_api_gateway_proposal_endpoints_rbac_and_flow():
    """
    Step 7: Test API Gateway endpoints for RBAC and proposal approval flow.
    """
    app = create_app()
    client = TestClient(app)

    # 1. Regular user gets 403 Forbidden when attempting to approve
    regular_user = CurrentUser(user_id=1, role="user", email="user@example.com")
    app.dependency_overrides[get_current_user] = lambda: regular_user

    resp = client.post("/api/v1/proposals/TEST-PROP-001/approve", json={})
    assert resp.status_code == 403
    assert "Only warehouse_manager or admin" in resp.json()["detail"]

    # 2. Regular user gets 403 Forbidden when attempting to reject
    resp = client.post("/api/v1/proposals/TEST-PROP-001/reject", json={"rejection_reason": "No right"})
    assert resp.status_code == 403

    # 3. Warehouse manager calling approve successfully through mock gRPC stub
    manager_user = CurrentUser(user_id=99, role="warehouse_manager", email="wm@example.com")
    app.dependency_overrides[get_current_user] = lambda: manager_user

    mock_row = inventory_pb2.DraftProposalRow(
        proposal_id="TEST-PROP-001",
        proposal_type="DraftAdjustmentProposal",
        sku_code="101",
        current_quantity=50,
        proposed_quantity=70,
        adjustment=20,
        reason="Manager approved adjustment",
        requested_by="AI_BOT",
        status="EXECUTED",
        created_at=datetime.now(timezone.utc).isoformat(),
        approved_by="99",
        approved_at=datetime.now(timezone.utc).isoformat(),
        executed_at=datetime.now(timezone.utc).isoformat(),
        executed_by="99",
    )

    mock_grpc_resp = inventory_pb2.ApproveDraftProposalResponse(
        success=True,
        message="Proposal approved and executed successfully",
        proposal=mock_row,
        transaction_id=1001,
    )

    with patch("api_gateway.routes.inventory_stub") as mock_stub_factory:
        mock_stub = MagicMock()
        mock_stub_factory.return_value.__enter__.return_value = mock_stub
        mock_stub.ApproveDraftProposal.return_value = mock_grpc_resp

        resp = client.post(
            "/api/v1/proposals/TEST-PROP-001/approve",
            json={"digital_signature": "TEST-SIG"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["proposal"]["status"] == "EXECUTED"
        assert data["transaction_id"] == 1001

    # Clean up overrides
    app.dependency_overrides.clear()


# ==============================================================================
# TASK-070: Maker Cancel & Idempotent Approval Workflow (DOM-05 / TECH-02)
# ==============================================================================

def test_cancel_and_idempotent_proposal_workflow(db_session):
    """
    Acceptance Criteria (TASK-070 / DOM-05 / TECH-02):
    1. Maker Cancel: Cho phép người tạo tự hủy đề xuất khi status == 'DRAFT_PROPOSAL'.
       Người khác không phải creator không có quyền hủy (PermissionError / 403).
    2. Idempotent Approve: Khi đề xuất đã ở trạng thái 'EXECUTED', gọi approve lần 2
       trả về 200 OK idempotent (không quăng lỗi 400 Bad Request).
    """
    repo = InventoryRepo(db_session)
    service = InventoryService(repo)

    # 1. Test Maker Cancel: Creator cancels their own proposal
    proposal_cancel = DraftProposalModel(
        proposal_id="PROP-CANCEL-001",
        proposal_type="DraftAdjustmentProposal",
        sku_code="101",
        current_quantity=50,
        proposed_quantity=60,
        adjustment=10,
        reason="Mistake by AI Agent",
        requested_by="AGENT_BOT_01",
        status="DRAFT_PROPOSAL",
    )
    repo.save_draft_proposal(proposal_cancel)

    # Non-creator attempts to cancel -> PermissionError
    with pytest.raises(PermissionError) as exc_info:
        service.cancel_draft_proposal(
            proposal_id="PROP-CANCEL-001",
            cancelled_by="OTHER_USER",
            cancellation_reason="Trying to cancel someone else's proposal",
        )
    assert "Only creator 'AGENT_BOT_01' can cancel" in str(exc_info.value)

    # Creator cancels their own proposal -> Success
    cancelled_prop = service.cancel_draft_proposal(
        proposal_id="PROP-CANCEL-001",
        cancelled_by="AGENT_BOT_01",
        cancellation_reason="Detected duplicate proposal",
    )
    assert cancelled_prop.status == "CANCELLED"
    assert "Detected duplicate proposal" in cancelled_prop.rejection_reason

    # Terminal state check: cannot approve a CANCELLED proposal
    with pytest.raises(ValueError) as val_err:
        service.approve_draft_proposal("PROP-CANCEL-001", approved_by="MANAGER_01")
    assert "Proposal cannot be approved in state CANCELLED" in str(val_err.value)

    # 2. Test Idempotent Approve:
    proposal_exec = DraftProposalModel(
        proposal_id="PROP-EXEC-002",
        proposal_type="DraftAdjustmentProposal",
        sku_code="101",
        current_quantity=50,
        proposed_quantity=70,
        adjustment=20,
        reason="Valid count adjustment",
        requested_by="AGENT_BOT_02",
        status="DRAFT_PROPOSAL",
    )
    repo.save_draft_proposal(proposal_exec)

    # First approval -> transitions to EXECUTED
    prop_approved, tx1 = service.approve_draft_proposal("PROP-EXEC-002", approved_by="MANAGER_01")
    assert prop_approved.status == "EXECUTED"

    # Second approval (e.g. network retry) -> Idempotent success without 400 Bad Request error
    prop_retry, tx2 = service.approve_draft_proposal("PROP-EXEC-002", approved_by="MANAGER_01")
    assert prop_retry.status == "EXECUTED"
    assert prop_retry.proposal_id == "PROP-EXEC-002"

    # 3. Test gRPC and Gateway Cancel Endpoint Flow
    app = create_app()
    client = TestClient(app)

    creator_user = CurrentUser(user_id=10, role="user", email="creator@example.com")
    app.dependency_overrides[get_current_user] = lambda: creator_user

    mock_row_cancelled = inventory_pb2.DraftProposalRow(
        proposal_id="PROP-CANCEL-001",
        proposal_type="DraftAdjustmentProposal",
        sku_code="101",
        current_quantity=50,
        proposed_quantity=60,
        adjustment=10,
        reason="Mistake",
        requested_by="10",
        status="CANCELLED",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    mock_grpc_cancel_resp = inventory_pb2.CancelDraftProposalResponse(
        success=True,
        message="Proposal cancelled successfully",
        proposal=mock_row_cancelled,
    )

    with patch("api_gateway.routes.inventory_stub") as mock_stub_factory:
        mock_stub = MagicMock()
        mock_stub_factory.return_value.__enter__.return_value = mock_stub
        mock_stub.CancelDraftProposal.return_value = mock_grpc_cancel_resp

        resp = client.post(
            "/api/v1/proposals/PROP-CANCEL-001/cancel",
            json={"cancellation_reason": "I made a mistake"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["proposal"]["status"] == "CANCELLED"

    app.dependency_overrides.clear()

