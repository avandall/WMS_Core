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

    def test_cycle_count_location_freeze_and_unfreeze_lifecycle(self) -> None:
        """TASK-089: Cycle count start freezes locations; approve/cancel/reject unfreezes them."""
        from unittest.mock import MagicMock
        mock_inv_repo = MagicMock()

        items = [
            CycleCountItem(
                item_id="ITEM-101",
                product_id=500,
                location_id="101",
                system_qty=50,
            ),
            CycleCountItem(
                item_id="ITEM-102",
                product_id=501,
                location_id="102",
                system_qty=30,
            ),
        ]

        service = CycleCountService(inventory_repo=mock_inv_repo)
        service.create_cycle_count_sheet(
            cycle_count_id="CC-FREEZE-001",
            warehouse_id=1,
            title="Freeze Test",
            items=items,
            discrepancy_qty_threshold=0,
        )

        # 1. Starting cycle count should freeze locations (is_counting=True)
        service.start_cycle_count("CC-FREEZE-001")
        mock_inv_repo.set_location_counting.assert_called_with(
            warehouse_id=1,
            position_ids=[101, 102],
            is_counting=True,
        )

        # 2. Record counts with discrepancy and submit -> PENDING_SUPERVISOR_APPROVAL
        service.record_counts("CC-FREEZE-001", {"ITEM-101": 55, "ITEM-102": 30})
        service.submit_counts("CC-FREEZE-001")

        # 3. Approving cycle count should unfreeze locations (is_counting=False)
        mock_inv_repo.set_location_counting.reset_mock()
        service.approve_cycle_count("CC-FREEZE-001", supervisor_id="sup_bob")
        mock_inv_repo.set_location_counting.assert_called_with(
            warehouse_id=1,
            position_ids=[101, 102],
            is_counting=False,
        )

    def test_cycle_count_cancel_and_reject_unfreeze_locations(self) -> None:
        """TASK-089: Cancelling or rejecting a cycle count sheet unfreezes locations."""
        from unittest.mock import MagicMock
        mock_inv_repo = MagicMock()

        items = [
            CycleCountItem(
                item_id="ITEM-201",
                product_id=600,
                location_id="201",
                system_qty=40,
            ),
        ]

        # Case A: Cancel
        service = CycleCountService(inventory_repo=mock_inv_repo)
        service.create_cycle_count_sheet(
            cycle_count_id="CC-CANCEL-001",
            warehouse_id=1,
            title="Cancel Test",
            items=items,
        )
        service.start_cycle_count("CC-CANCEL-001")
        mock_inv_repo.set_location_counting.assert_called_with(
            warehouse_id=1,
            position_ids=[201],
            is_counting=True,
        )

        mock_inv_repo.set_location_counting.reset_mock()
        service.cancel_cycle_count("CC-CANCEL-001", cancelled_by="sup_bob", reason="Recount abandoned")
        mock_inv_repo.set_location_counting.assert_called_with(
            warehouse_id=1,
            position_ids=[201],
            is_counting=False,
        )

        # Case B: Reject
        mock_inv_repo.set_location_counting.reset_mock()
        service.create_cycle_count_sheet(
            cycle_count_id="CC-REJECT-LOC-001",
            warehouse_id=1,
            title="Reject Loc Test",
            items=items,
            discrepancy_qty_threshold=0,
        )
        service.start_cycle_count("CC-REJECT-LOC-001")
        service.record_counts("CC-REJECT-LOC-001", {"ITEM-201": 20})
        service.submit_counts("CC-REJECT-LOC-001")

        mock_inv_repo.set_location_counting.reset_mock()
        service.reject_cycle_count("CC-REJECT-LOC-001", supervisor_id="sup_bob", reason="Recount required")
        mock_inv_repo.set_location_counting.assert_called_with(
            warehouse_id=1,
            position_ids=[201],
            is_counting=False,
        )


def test_empty_bin_freeze_locks_position_and_blocks_putaway():
    """TASK-096: Freezing an empty bin sets is_counting on PositionModel and rejects putaway."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.shared.core.database import Base, import_all_models
    from app.shared.domain.business_exceptions import LocationFrozenError
    from app.modules.inventory.infrastructure.models.position import PositionModel
    from app.modules.inventory.infrastructure.repositories.inventory_repo import InventoryRepo

    engine = create_engine("sqlite:///:memory:", echo=False)
    import_all_models()
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Create empty physical position (no inventory_locations row)
    pos = PositionModel(id=901, warehouse_id=1, code="A-EMPTY-01", is_counting=False)
    session.add(pos)
    session.commit()

    repo = InventoryRepo(session)

    # 1. Freeze the empty bin
    repo.set_location_counting(warehouse_id=1, position_ids=[901], is_counting=True)

    session.expire_all()
    updated_pos = session.query(PositionModel).filter_by(id=901).one()
    assert updated_pos.is_counting is True
    assert repo.is_position_counting(warehouse_id=1, position_id=901) is True

    # 2. Forklift driver tries to putaway goods into this frozen empty bin -> Must raise LocationFrozenError
    import pytest
    with pytest.raises(LocationFrozenError) as exc_info:
        repo.adjust_location_quantity(
            warehouse_id=1,
            position_id=901,
            product_id=500,
            quantity_delta=10,
            lpn="LPN-PUTAWAY-01",
        )
    assert "frozen for cycle counting" in str(exc_info.value)

    # 3. Unfreeze position
    repo.set_location_counting(warehouse_id=1, position_ids=[901], is_counting=False)
    session.expire_all()
    assert repo.is_position_counting(warehouse_id=1, position_id=901) is False

    # 4. Now putaway succeeds
    res = repo.adjust_location_quantity(
        warehouse_id=1,
        position_id=901,
        product_id=500,
        quantity_delta=10,
        lpn="LPN-PUTAWAY-01",
    )
    assert res["quantity"] == 10
    session.close()


def test_move_stock_into_or_out_of_frozen_position_fails():
    """TASK-096: move_location_stock rejects transfer when either source or destination is frozen."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.shared.core.database import Base, import_all_models
    from app.shared.domain.business_exceptions import LocationFrozenError
    from app.modules.inventory.infrastructure.models.position import PositionModel
    from app.modules.inventory.infrastructure.repositories.inventory_repo import InventoryRepo

    engine = create_engine("sqlite:///:memory:", echo=False)
    import_all_models()
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Source position (has stock) and Destination position (initially empty)
    pos_src = PositionModel(id=902, warehouse_id=1, code="A-SRC-01", is_counting=False)
    pos_dst = PositionModel(id=903, warehouse_id=1, code="A-DST-01", is_counting=False)
    session.add_all([pos_src, pos_dst])
    session.commit()

    repo = InventoryRepo(session)
    # Populate initial stock at source
    repo.adjust_location_quantity(
        warehouse_id=1,
        position_id=902,
        product_id=500,
        quantity_delta=20,
        lpn="LPN-SRC",
    )

    # Freeze destination position 903
    repo.set_location_counting(warehouse_id=1, position_ids=[903], is_counting=True)

    import pytest
    # Moving into frozen destination 903 must fail
    with pytest.raises(LocationFrozenError) as exc_info:
        repo.move_location_stock(
            product_id=500,
            from_warehouse_id=1,
            from_position_id=902,
            to_position_id=903,
            quantity=5,
            lpn="LPN-SRC",
        )
    assert "Destination position 903" in str(exc_info.value)
    assert "frozen for cycle counting" in str(exc_info.value)

    # Unfreeze 903, freeze source position 902
    repo.set_location_counting(warehouse_id=1, position_ids=[903], is_counting=False)
    repo.set_location_counting(warehouse_id=1, position_ids=[902], is_counting=True)

    # Moving out of frozen source 902 must fail
    with pytest.raises(LocationFrozenError) as exc_info:
        repo.move_location_stock(
            product_id=500,
            from_warehouse_id=1,
            from_position_id=902,
            to_position_id=903,
            quantity=5,
            lpn="LPN-SRC",
        )
    assert "Source position 902" in str(exc_info.value)
    assert "frozen for cycle counting" in str(exc_info.value)

    # Unfreeze 902 -> now moving succeeds
    repo.set_location_counting(warehouse_id=1, position_ids=[902], is_counting=False)
    src_res, dst_res = repo.move_location_stock(
        product_id=500,
        from_warehouse_id=1,
        from_position_id=902,
        to_position_id=903,
        quantity=5,
        lpn="LPN-SRC",
    )
    assert src_res["quantity"] == 15
    assert dst_res["quantity"] == 5
    session.close()




