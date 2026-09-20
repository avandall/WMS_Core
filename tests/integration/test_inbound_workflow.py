"""
Integration Test Suite for Inbound Workflow (TASK-010).

Covers the 3-step inbound workflow:
1. Dock Reception (Inbound ASN/PO + Dock Appointment)
2. QA & Quarantine Inspection (Goods enter QUARANTINED state, then transition to AVAILABLE upon passing QA)
3. Directed Putaway Engine (ABC velocity & volume/weight capacity constraints)
"""

from datetime import datetime, timedelta, timezone
import pytest

from app.modules.documents.domain.entities.inbound_shipment import (
    DockAppointment,
    InboundItem,
    InboundShipment,
    InboundStatus,
    QAResultStatus,
)
from app.modules.positions.application.services.putaway_engine import (
    PositionCapacityInfo,
    PutawayEngine,
    PutawayRecommendation,
    PutawayRequest,
)
from app.shared.domain.business_exceptions import (
    BusinessRuleViolationError,
    InvalidDocumentStatusError,
    InvalidIDError,
    InvalidQuantityError,
    ValidationError,
)


class TestInboundASNAndDockAppointment:
    """Test Step 1: ASN / PO creation and Dock Appointment scheduling."""

    def test_create_inbound_shipment_with_dock_appointment(self):
        shipment = InboundShipment(
            shipment_id=101,
            asn_number="ASN-2026-001",
            destination_warehouse_id=1,
            po_number="PO-2026-999",
            supplier_id=50,
            created_by="warehouse_mgr",
        )
        assert shipment.shipment_id == 101
        assert shipment.asn_number == "ASN-2026-001"
        assert shipment.status == InboundStatus.DRAFT

        item1 = InboundItem(
            product_id=10,
            expected_qty=100,
            unit_weight=2.5,
            unit_volume=0.01,
            abc_classification="A",
        )
        item2 = InboundItem(
            product_id=11,
            expected_qty=50,
            unit_weight=5.0,
            unit_volume=0.03,
            abc_classification="B",
        )
        shipment.add_item(item1)
        shipment.add_item(item2)
        assert len(shipment.items) == 2

        # Schedule dock appointment
        appt_time = datetime.now(timezone.utc) + timedelta(hours=2)
        appt = shipment.schedule_dock_appointment(
            dock_door="DOCK-01",
            appointment_time=appt_time,
            carrier="FastLogistics",
            driver_name="Nguyen Van A",
            vehicle_plate="29C-12345",
        )
        assert appt.dock_door == "DOCK-01"
        assert appt.status == "SCHEDULED"
        assert shipment.status == InboundStatus.SCHEDULED

        # Confirm dock arrival (Check-in)
        shipment.confirm_dock_arrival()
        assert appt.status == "CHECKED_IN"
        assert shipment.status == InboundStatus.ARRIVED


class TestQAAndQuarantineWorkflow:
    """Test Step 2: Receiving & QA Quarantine workflow (AC2)."""

    def test_receiving_goods_places_inventory_in_quarantine(self):
        shipment = InboundShipment(
            shipment_id=102,
            asn_number="ASN-2026-002",
            destination_warehouse_id=1,
        )
        item = InboundItem(
            product_id=20,
            expected_qty=200,
            unit_weight=1.0,
            unit_volume=0.005,
            abc_classification="A",
        )
        shipment.add_item(item)
        shipment.schedule_dock_appointment(dock_door="DOCK-02", appointment_time=datetime.now(timezone.utc))
        shipment.confirm_dock_arrival()

        # Receive goods at dock
        shipment.receive_goods({20: 200})
        assert shipment.status == InboundStatus.RECEIVING
        assert item.received_qty == 200
        # AC2 Requirement: Received inventory must initially be QUARANTINED
        assert item.inventory_status == "QUARANTINED"
        assert item.qa_status == QAResultStatus.PENDING

    def test_qa_inspection_promotes_passed_goods_to_available(self):
        shipment = InboundShipment(
            shipment_id=103,
            asn_number="ASN-2026-003",
            destination_warehouse_id=1,
        )
        item_pass = InboundItem(
            product_id=30,
            expected_qty=100,
            unit_weight=2.0,
            unit_volume=0.01,
            abc_classification="A",
        )
        item_fail = InboundItem(
            product_id=31,
            expected_qty=50,
            unit_weight=3.0,
            unit_volume=0.02,
            abc_classification="C",
        )
        shipment.add_item(item_pass)
        shipment.add_item(item_fail)

        shipment.schedule_dock_appointment("DOCK-01", datetime.now(timezone.utc))
        shipment.confirm_dock_arrival()
        shipment.receive_goods({30: 100, 31: 50})

        # QA inspection: item_pass 100% passed -> status AVAILABLE
        shipment.perform_qa_inspection(product_id=30, passed_qty=100, failed_qty=0)
        assert item_pass.qa_status == QAResultStatus.PASSED
        assert item_pass.inventory_status == "AVAILABLE"
        assert item_pass.passed_qa_qty == 100

        # QA inspection: item_fail 100% failed -> status QUARANTINED
        shipment.perform_qa_inspection(product_id=31, passed_qty=0, failed_qty=50)
        assert item_fail.qa_status == QAResultStatus.FAILED
        assert item_fail.inventory_status == "QUARANTINED"
        assert item_fail.failed_qa_qty == 50

        # Complete QA process for shipment
        shipment.complete_qa_process()
        assert shipment.status == InboundStatus.COMPLETED
        assert shipment.appointment.status == "COMPLETED"

    def test_qa_inspection_exceeding_received_qty_raises_error(self):
        shipment = InboundShipment(shipment_id=104, asn_number="ASN-2026-004", destination_warehouse_id=1)
        item = InboundItem(product_id=40, expected_qty=50, unit_weight=1.0, unit_volume=0.01)
        shipment.add_item(item)
        shipment.schedule_dock_appointment("DOCK-01", datetime.now(timezone.utc))
        shipment.confirm_dock_arrival()
        shipment.receive_goods({40: 50})

        with pytest.raises(BusinessRuleViolationError, match="exceeds received quantity"):
            shipment.perform_qa_inspection(product_id=40, passed_qty=40, failed_qty=20)


class TestDirectedPutawayEngine:
    """Test Step 3: Directed Putaway Engine (AC3)."""

    @pytest.fixture
    def warehouse_positions(self):
        return [
            PositionCapacityInfo(
                position_id=1,
                code="A-01-01",
                warehouse_id=1,
                max_weight=1000.0,
                max_volume=5.0,
                current_weight=100.0,
                current_volume=0.5,
                zone="ZONE_A",
                position_type="STORAGE",
            ),
            PositionCapacityInfo(
                position_id=2,
                code="A-01-02",
                warehouse_id=1,
                max_weight=50.0,  # Small weight capacity
                max_volume=0.2,   # Small volume capacity
                current_weight=0.0,
                current_volume=0.0,
                zone="ZONE_A",
                position_type="STORAGE",
            ),
            PositionCapacityInfo(
                position_id=3,
                code="C-05-01",
                warehouse_id=1,
                max_weight=2000.0,
                max_volume=10.0,
                current_weight=200.0,
                current_volume=1.0,
                zone="ZONE_C",
                position_type="STORAGE",
            ),
            PositionCapacityInfo(
                position_id=4,
                code="Q-01-01",
                warehouse_id=1,
                max_weight=5000.0,
                max_volume=20.0,
                current_weight=0.0,
                current_volume=0.0,
                zone="ZONE_Q",
                position_type="QUARANTINE",
            ),
        ]

    def test_putaway_engine_recommends_matching_abc_zone_and_capacity(self, warehouse_positions):
        # Product class A: 100 units, weight 2.0kg/unit (total 200kg), volume 0.01m3/unit (total 1.0m3)
        request_a = PutawayRequest(
            product_id=30,
            quantity=100,
            unit_weight=2.0,
            unit_volume=0.01,
            abc_classification="A",
        )

        recs = PutawayEngine.suggest_putaway_location(request_a, warehouse_positions)
        assert len(recs) > 0
        # Position 1 (A-01-01 in ZONE_A) must be ranked first due to exact ABC zone match and sufficient capacity
        top_rec = recs[0]
        assert top_rec.position_id == 1
        assert top_rec.position_code == "A-01-01"
        assert top_rec.zone == "ZONE_A"

        # Position 2 (A-01-02) cannot fit 200kg/1.0m3 so it should be excluded
        rec_ids = [r.position_id for r in recs]
        assert 2 not in rec_ids
        # Position 4 (QUARANTINE) should be excluded because preferred position_type is STORAGE
        assert 4 not in rec_ids

    def test_putaway_engine_prioritizes_zone_c_for_class_c_products(self, warehouse_positions):
        request_c = PutawayRequest(
            product_id=31,
            quantity=50,
            unit_weight=1.0,
            unit_volume=0.02,
            abc_classification="C",
        )

        recs = PutawayEngine.suggest_putaway_location(request_c, warehouse_positions)
        assert len(recs) > 0
        # Top recommendation for ABC 'C' should be Position 3 in ZONE_C
        assert recs[0].position_id == 3
        assert recs[0].position_code == "C-05-01"

    def test_putaway_engine_filters_out_overcapacity_positions(self, warehouse_positions):
        # Heavy/Bulky request: 1000 units x 5.0kg = 5000kg (exceeds all STORAGE positions' available weights)
        heavy_request = PutawayRequest(
            product_id=99,
            quantity=1000,
            unit_weight=5.0,
            unit_volume=0.1,
            abc_classification="A",
        )

        recs = PutawayEngine.suggest_putaway_location(heavy_request, warehouse_positions)
        assert len(recs) == 0


class TestInboundWorkflowEndToEnd:
    """Complete End-to-End Test integrating Step 1, 2, and 3."""

    def test_full_inbound_dock_to_putaway_pipeline(self):
        # 1. Dock Reception & ASN Creation
        shipment = InboundShipment(
            shipment_id=200,
            asn_number="ASN-E2E-2026",
            destination_warehouse_id=1,
            supplier_id=10,
        )
        item = InboundItem(
            product_id=500,
            expected_qty=100,
            unit_weight=2.0,
            unit_volume=0.01,
            abc_classification="A",
        )
        shipment.add_item(item)
        shipment.schedule_dock_appointment("DOCK-03", datetime.now(timezone.utc))
        shipment.confirm_dock_arrival()

        # 2. Receive Goods & QA Inspection
        shipment.receive_goods({500: 100})
        assert item.inventory_status == "QUARANTINED"  # Initially quarantined

        shipment.perform_qa_inspection(product_id=500, passed_qty=100, failed_qty=0)
        assert item.inventory_status == "AVAILABLE"
        shipment.complete_qa_process()
        assert shipment.status == InboundStatus.COMPLETED

        # 3. Directed Putaway Recommendation for passed items
        putaway_req = PutawayRequest(
            product_id=item.product_id,
            quantity=item.passed_qa_qty,
            unit_weight=item.unit_weight,
            unit_volume=item.unit_volume,
            abc_classification=item.abc_classification,
        )

        candidates = [
            PositionCapacityInfo(1, "A-01", 1, max_weight=500.0, max_volume=2.0, zone="ZONE_A"),
            PositionCapacityInfo(2, "B-01", 1, max_weight=500.0, max_volume=2.0, zone="ZONE_B"),
        ]

        recommendations = PutawayEngine.suggest_putaway_location(putaway_req, candidates)
        assert len(recommendations) == 2
        assert recommendations[0].position_code == "A-01"
        assert recommendations[0].zone == "ZONE_A"
