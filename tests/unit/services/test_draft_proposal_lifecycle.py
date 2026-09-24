"""
Unit tests for TASK-058 / CRIT-08: DraftProposalModel Lifecycle & Maker-Checker State Machine.
"""
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.modules.inventory.infrastructure.models.draft_proposal import DraftProposalModel
from app.shared.core.database import Base


def test_draft_proposal_model_has_required_columns():
    """Verify DraftProposalModel has all required governance and audit fields."""
    required_fields = [
        "proposal_id",
        "proposal_type",
        "sku_code",
        "current_quantity",
        "proposed_quantity",
        "adjustment",
        "reason",
        "requested_by",
        "status",
        "created_at",
        "approved_by",
        "approved_at",
        "rejection_reason",
        "executed_at",
        "executed_by",
        "digital_signature",
    ]
    for field in required_fields:
        assert hasattr(DraftProposalModel, field), f"Missing required column: {field}"


def test_draft_proposal_valid_approval_and_execution_lifecycle():
    """Test standard happy path: DRAFT_PROPOSAL -> APPROVED -> EXECUTED."""
    proposal = DraftProposalModel(
        proposal_id="PROP-1001",
        proposal_type="DraftAdjustmentProposal",
        sku_code="LAP-001",
        current_quantity=10,
        proposed_quantity=20,
        adjustment=10,
        reason="Cycle count reconciliation",
        requested_by="operator_john",
        status="DRAFT_PROPOSAL",
    )

    assert proposal.status == "DRAFT_PROPOSAL"
    assert proposal.approved_by is None
    assert proposal.approved_at is None
    assert proposal.executed_by is None
    assert proposal.executed_at is None

    # Step 1: Warehouse Manager approves
    proposal.approve("manager_alice")
    assert proposal.status == "APPROVED"
    assert proposal.approved_by == "manager_alice"
    assert proposal.approved_at is not None

    # Step 2: System or Operator marks executed
    proposal.mark_executed("inventory_worker")
    assert proposal.status == "EXECUTED"
    assert proposal.executed_by == "inventory_worker"
    assert proposal.executed_at is not None


def test_draft_proposal_rejection_lifecycle():
    """Test rejection path: DRAFT_PROPOSAL -> REJECTED."""
    proposal = DraftProposalModel(
        proposal_id="PROP-1002",
        proposal_type="DraftAdjustmentProposal",
        sku_code="MOB-003",
        current_quantity=50,
        proposed_quantity=0,
        adjustment=-50,
        reason="Suspected theft",
        requested_by="operator_bob",
        status="DRAFT_PROPOSAL",
    )

    proposal.reject("Variance exceeded without physical audit report", reviewer="manager_alice")
    assert proposal.status == "REJECTED"
    assert proposal.rejection_reason == "Variance exceeded without physical audit report"
    assert proposal.approved_by == "manager_alice"
    assert proposal.approved_at is not None


def test_draft_proposal_terminal_state_cannot_transition_back():
    """
    Acceptance Criteria (TASK-058 / CRIT-08):
    Chặn chuyển trạng thái sai logic: Phiếu đã REJECTED hoặc EXECUTED
    không thể chuyển ngược lại DRAFT_PROPOSAL.
    """
    # 1. Test REJECTED cannot transition back to DRAFT_PROPOSAL or APPROVED
    proposal_rejected = DraftProposalModel(
        proposal_id="PROP-1003",
        proposal_type="DraftAdjustmentProposal",
        sku_code="SKU-01",
        status="DRAFT_PROPOSAL",
    )
    proposal_rejected.reject("Invalid request")
    assert proposal_rejected.status == "REJECTED"

    with pytest.raises(ValueError, match="Invalid status transition from REJECTED to DRAFT_PROPOSAL"):
        proposal_rejected.status = "DRAFT_PROPOSAL"

    with pytest.raises(ValueError, match="Invalid status transition from REJECTED to APPROVED"):
        proposal_rejected.status = "APPROVED"

    # 2. Test EXECUTED cannot transition back to DRAFT_PROPOSAL or REJECTED
    proposal_executed = DraftProposalModel(
        proposal_id="PROP-1004",
        proposal_type="DraftAdjustmentProposal",
        sku_code="SKU-02",
        status="DRAFT_PROPOSAL",
    )
    proposal_executed.approve("manager_bob")
    proposal_executed.mark_executed("system")
    assert proposal_executed.status == "EXECUTED"

    with pytest.raises(ValueError, match="Invalid status transition from EXECUTED to DRAFT_PROPOSAL"):
        proposal_executed.status = "DRAFT_PROPOSAL"

    with pytest.raises(ValueError, match="Invalid status transition from EXECUTED to REJECTED"):
        proposal_executed.status = "REJECTED"


def test_draft_proposal_invalid_status_value():
    """Setting completely invalid status raises ValueError."""
    proposal = DraftProposalModel(
        proposal_id="PROP-1005",
        proposal_type="DraftAdjustmentProposal",
        sku_code="SKU-03",
        status="DRAFT_PROPOSAL",
    )
    with pytest.raises(ValueError, match="Invalid status 'PENDING_HACK'"):
        proposal.status = "PENDING_HACK"


def test_draft_proposal_database_persistence():
    """Verify table creation and database persistence in SQLite."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine, tables=[DraftProposalModel.__table__])

    Session = sessionmaker(bind=engine)
    session = Session()

    proposal = DraftProposalModel(
        proposal_id="PROP-PERSIST-01",
        proposal_type="DraftMovementProposal",
        sku_code="LAP-PRO-15",
        current_quantity=100,
        proposed_quantity=80,
        adjustment=-20,
        reason="Relocate to Zone A",
        requested_by="ai_agent",
        status="DRAFT_PROPOSAL",
        digital_signature="abc123hmacsignature",
    )
    session.add(proposal)
    session.commit()

    saved = session.query(DraftProposalModel).filter_by(proposal_id="PROP-PERSIST-01").first()
    assert saved is not None
    assert saved.sku_code == "LAP-PRO-15"
    assert saved.digital_signature == "abc123hmacsignature"
    assert saved.status == "DRAFT_PROPOSAL"

    # Update through approval
    saved.approve("supervisor_dave")
    session.commit()

    reloaded = session.query(DraftProposalModel).filter_by(proposal_id="PROP-PERSIST-01").first()
    assert reloaded.status == "APPROVED"
    assert reloaded.approved_by == "supervisor_dave"
    assert reloaded.approved_at is not None

    session.close()
