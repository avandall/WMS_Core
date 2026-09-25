"""Unit tests for Blind Cycle Counting & Discrepancy Approval (TASK-012)."""

import pytest
from app.modules.documents.application.services.cycle_count_service import (
    CycleCountAdjustmentPayload,
    CycleCountService,
)
from app.modules.documents.domain.entities.cycle_count import (
    BlindCountItem,
    CycleCountItem,
    CycleCountSheet,
    CycleCountStatus,
    DiscrepancyType,
)
from app.shared.domain.business_exceptions import (
    BusinessRuleViolationError,
    EntityAlreadyExistsError,
    EntityNotFoundError,
    InvalidDocumentStatusError,
    InvalidIDError,
    InvalidQuantityError,
    ValidationError,
)


class TestCycleCounting:
    """Test suite for CycleCountSheet domain logic and CycleCountService."""

    @pytest.fixture(autouse=True)
    def setup_sqlite_tables(self):
        from app.shared.core.database import Base, engine
        from app.modules.documents.infrastructure.models.cycle_count_sheet import CycleCountSheetModel
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)


    @pytest.fixture
    def service(self) -> CycleCountService:
        return CycleCountService()


    @pytest.fixture
    def sample_items(self) -> list[CycleCountItem]:
        return [
            CycleCountItem(
                item_id="ITEM-001",
                product_id=101,
                location_id="A-01-01",
                system_qty=100,
                lot_number="LOT-2026-A",
                unit_cost=10.0,
            ),
            CycleCountItem(
                item_id="ITEM-002",
                product_id=102,
                location_id="A-01-02",
                system_qty=50,
                lot_number="LOT-2026-B",
                unit_cost=20.0,
            ),
        ]

    def test_create_cycle_count_sheet(
        self, service: CycleCountService, sample_items: list[CycleCountItem]
    ) -> None:
        """Test creating a cycle count sheet."""
        sheet = service.create_cycle_count_sheet(
            cycle_count_id="CC-2026-001",
            warehouse_id=1,
            title="Monthly A-Zone Cycle Count",
            items=sample_items,
            assigned_to="staff_john",
            discrepancy_qty_threshold=2,
            discrepancy_value_threshold=50.0,
        )

        assert sheet.cycle_count_id == "CC-2026-001"
        assert sheet.warehouse_id == 1
        assert sheet.status == CycleCountStatus.DRAFT
        assert len(sheet.items) == 2
        assert sheet.assigned_to == "staff_john"

    def test_duplicate_sheet_creation_fails(
        self, service: CycleCountService, sample_items: list[CycleCountItem]
    ) -> None:
        """Test creating a sheet with duplicate ID raises EntityAlreadyExistsError."""
        service.create_cycle_count_sheet(
            cycle_count_id="CC-2026-001",
            warehouse_id=1,
            title="Count 1",
            items=sample_items,
        )
        with pytest.raises(EntityAlreadyExistsError):
            service.create_cycle_count_sheet(
                cycle_count_id="CC-2026-001",
                warehouse_id=1,
                title="Count 2",
                items=sample_items,
            )

    def test_blind_count_sheet_hides_system_qty(
        self, service: CycleCountService, sample_items: list[CycleCountItem]
    ) -> None:
        """AC1: Blind count sheet provided to counter staff strictly hides system_qty."""
        sheet = service.create_cycle_count_sheet(
            cycle_count_id="CC-BLIND-001",
            warehouse_id=1,
            title="Blind Count Test",
            items=sample_items,
        )
        service.start_cycle_count("CC-BLIND-001", assigned_to="counter_alice")

        blind_items = service.get_blind_count_sheet("CC-BLIND-001")
        assert len(blind_items) == 2

        for b_item in blind_items:
            assert isinstance(b_item, BlindCountItem)
            # Verify system_qty attribute does NOT exist on BlindCountItem
            assert not hasattr(b_item, "system_qty")
            assert b_item.item_id in ("ITEM-001", "ITEM-002")
            assert b_item.product_id in (101, 102)
            assert b_item.is_counted is False

    def test_record_counts_within_threshold_auto_approves(
        self, service: CycleCountService, sample_items: list[CycleCountItem]
    ) -> None:
        """Test recording counts within threshold auto-approves sheet."""
        sheet = service.create_cycle_count_sheet(
            cycle_count_id="CC-TOLERANCE-001",
            warehouse_id=1,
            title="Tolerance Count Test",
            items=sample_items,
            discrepancy_qty_threshold=2,  # Allow up to 2 units deviation
            discrepancy_value_threshold=50.0,
        )
        service.start_cycle_count("CC-TOLERANCE-001")

        # ITEM-001: system=100, counted=99 (discrepancy=-1, <= threshold 2)
        # ITEM-002: system=50, counted=50 (discrepancy=0)
        service.record_counts(
            "CC-TOLERANCE-001",
            {"ITEM-001": 99, "ITEM-002": 50},
        )
        updated_sheet = service.submit_counts("CC-TOLERANCE-001")

        assert updated_sheet.status == CycleCountStatus.APPROVED
        assert updated_sheet.approved_by == "system"

        adjustments = service.generate_inventory_adjustments("CC-TOLERANCE-001")
        assert len(adjustments) == 1
        assert adjustments[0].product_id == 101
        assert adjustments[0].discrepancy_qty == -1

    def test_record_counts_exceeding_threshold_requires_supervisor_approval(
        self, service: CycleCountService, sample_items: list[CycleCountItem]
    ) -> None:
        """AC2: Any discrepancy exceeding threshold transitions status to PENDING_SUPERVISOR_APPROVAL."""
        sheet = service.create_cycle_count_sheet(
            cycle_count_id="CC-EXCEED-001",
            warehouse_id=1,
            title="Exceed Threshold Test",
            items=sample_items,
            discrepancy_qty_threshold=2,  # Max allowed quantity deviation: 2
            discrepancy_value_threshold=30.0,
        )
        service.start_cycle_count("CC-EXCEED-001")

        # ITEM-001: system=100, counted=90 (discrepancy=-10, abs(10) > threshold 2)
        service.record_counts(
            "CC-EXCEED-001",
            {"ITEM-001": 90, "ITEM-002": 50},
        )
        updated_sheet = service.submit_counts("CC-EXCEED-001")

        assert updated_sheet.status == CycleCountStatus.PENDING_SUPERVISOR_APPROVAL

    def test_supervisor_approval_workflow(
        self, service: CycleCountService, sample_items: list[CycleCountItem]
    ) -> None:
        """Test full supervisor approval workflow for pending discrepancy."""
        service.create_cycle_count_sheet(
            cycle_count_id="CC-APPROVE-001",
            warehouse_id=1,
            title="Approval Workflow Test",
            items=sample_items,
            discrepancy_qty_threshold=0,  # Zero tolerance: any discrepancy requires approval
        )
        service.start_cycle_count("CC-APPROVE-001")
        service.record_counts("CC-APPROVE-001", {"ITEM-001": 105, "ITEM-002": 48})
        service.submit_counts("CC-APPROVE-001")

        sheet = service.get_cycle_count_sheet("CC-APPROVE-001")
        assert sheet.status == CycleCountStatus.PENDING_SUPERVISOR_APPROVAL

        # Supervisor approves
        approved_sheet = service.approve_cycle_count(
            "CC-APPROVE-001", supervisor_id="sup_bob", note="Approved after recount verification"
        )
        assert approved_sheet.status == CycleCountStatus.APPROVED
        assert approved_sheet.approved_by == "sup_bob"

        # Verify adjustment payloads can now be generated
        adjustments = service.generate_inventory_adjustments("CC-APPROVE-001")
        assert len(adjustments) == 2
        adj_map = {a.product_id: a.discrepancy_qty for a in adjustments}
        assert adj_map[101] == 5  # Surplus +5
        assert adj_map[102] == -2  # Shortage -2

    def test_supervisor_rejection_workflow(
        self, service: CycleCountService, sample_items: list[CycleCountItem]
    ) -> None:
        """Test supervisor rejection workflow."""
        service.create_cycle_count_sheet(
            cycle_count_id="CC-REJECT-001",
            warehouse_id=1,
            title="Rejection Test",
            items=sample_items,
            discrepancy_qty_threshold=0,
        )
        service.start_cycle_count("CC-REJECT-001")
        service.record_counts("CC-REJECT-001", {"ITEM-001": 80, "ITEM-002": 50})
        service.submit_counts("CC-REJECT-001")

        # Supervisor rejects
        rejected_sheet = service.reject_cycle_count(
            "CC-REJECT-001",
            supervisor_id="sup_bob",
            reason="Unexplained large shortage of 20 units. Re-count requested.",
        )
        assert rejected_sheet.status == CycleCountStatus.REJECTED
        assert rejected_sheet.rejection_reason == "Unexplained large shortage of 20 units. Re-count requested."

        # Cannot generate inventory adjustments for REJECTED count
        with pytest.raises(BusinessRuleViolationError):
            service.generate_inventory_adjustments("CC-REJECT-001")

    def test_uncounted_items_submission_fails(
        self, service: CycleCountService, sample_items: list[CycleCountItem]
    ) -> None:
        """Test submitting counts when some items are uncounted raises BusinessRuleViolationError."""
        service.create_cycle_count_sheet(
            cycle_count_id="CC-UNCOUNTED-001",
            warehouse_id=1,
            title="Partial Count Test",
            items=sample_items,
        )
        service.start_cycle_count("CC-UNCOUNTED-001")
        # Only record count for ITEM-001
        service.record_counts("CC-UNCOUNTED-001", {"ITEM-001": 100})

        with pytest.raises(BusinessRuleViolationError):
            service.submit_counts("CC-UNCOUNTED-001")

    def test_negative_counted_quantity_fails(
        self, service: CycleCountService, sample_items: list[CycleCountItem]
    ) -> None:
        """Test recording negative counted quantity raises InvalidQuantityError."""
        service.create_cycle_count_sheet(
            cycle_count_id="CC-NEG-001",
            warehouse_id=1,
            title="Negative Count Test",
            items=sample_items,
        )
        service.start_cycle_count("CC-NEG-001")

        with pytest.raises(InvalidQuantityError):
            service.record_counts("CC-NEG-001", {"ITEM-001": -5})

    def test_invalid_status_transitions(
        self, service: CycleCountService, sample_items: list[CycleCountItem]
    ) -> None:
        """Test invalid domain state transitions raise appropriate exceptions."""
        service.create_cycle_count_sheet(
            cycle_count_id="CC-STATE-001",
            warehouse_id=1,
            title="State Transition Test",
            items=sample_items,
        )

        # Cannot approve DRAFT sheet directly
        with pytest.raises(InvalidDocumentStatusError):
            service.approve_cycle_count("CC-STATE-001", supervisor_id="sup_bob")

        # Cannot record counts on DRAFT sheet before starting
        with pytest.raises(InvalidDocumentStatusError):
            service.record_counts("CC-STATE-001", {"ITEM-001": 100})

        # Cannot generate adjustments for DRAFT sheet
        with pytest.raises(BusinessRuleViolationError):
            service.generate_inventory_adjustments("CC-STATE-001")

    def test_cycle_count_survives_service_restart(
        self, test_session, sample_items: list[CycleCountItem]
    ) -> None:
        """Test cycle count sheet state persists in DB across service restarts."""
        service1 = CycleCountService(session=test_session)
        service1.create_cycle_count_sheet(
            cycle_count_id="CC-RS-001",
            warehouse_id=1,
            title="Restart Audit Test",
            items=sample_items,
            discrepancy_qty_threshold=5,
        )
        service1.start_cycle_count("CC-RS-001", assigned_to="staff_alex")
        service1.record_counts("CC-RS-001", {"ITEM-001": 110, "ITEM-002": 50})
        service1.submit_counts("CC-RS-001")

        # Simulate service restart: instantiate NEW CycleCountService instance
        service2 = CycleCountService(session=test_session)
        sheet2 = service2.get_cycle_count_sheet("CC-RS-001")
        assert sheet2.cycle_count_id == "CC-RS-001"
        assert sheet2.assigned_to == "staff_alex"
        assert sheet2.status == CycleCountStatus.PENDING_SUPERVISOR_APPROVAL
        assert len(sheet2.items) == 2
        assert sheet2.items[0].counted_qty == 110
        assert sheet2.items[0].discrepancy_qty == 10

    def test_cycle_count_auto_adjusts_inventory(
        self, sample_items: list[CycleCountItem]
    ) -> None:
        """TASK-042 [FLOW-04]: Cycle Count approved automatically adjusts inventory locations."""
        from unittest.mock import MagicMock
        mock_inv_repo = MagicMock()

        service = CycleCountService(inventory_repo=mock_inv_repo)
        service.create_cycle_count_sheet(
            cycle_count_id="CC-AUTO-001",
            warehouse_id=1,
            title="Auto Adjust Test",
            items=sample_items,
            discrepancy_qty_threshold=0,
        )
        service.start_cycle_count("CC-AUTO-001")
        service.record_counts("CC-AUTO-001", {"ITEM-001": 105, "ITEM-002": 50})
        service.submit_counts("CC-AUTO-001")

        service.approve_cycle_count("CC-AUTO-001", supervisor_id="sup_bob")

        mock_inv_repo.adjust_location_quantity.assert_called_once()
        call_kwargs = mock_inv_repo.adjust_location_quantity.call_args.kwargs
        assert call_kwargs["warehouse_id"] == 1
        assert call_kwargs["product_id"] == 101
        assert call_kwargs["quantity_delta"] == 5


