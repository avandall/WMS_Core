from datetime import datetime, timezone
import pytest

from app.modules.documents.application.services.packing_service import (
    CartonPackage,
    PackItem,
    PackingService,
    PackingStatus,
)
from app.modules.documents.application.services.wave_service import (
    BatchPickingTask,
    OrderItem,
    OutboundOrder,
    PickingWave,
    WaveService,
    WaveStatus,
)
from app.shared.domain.business_exceptions import (
    BusinessRuleViolationError,
    EntityNotFoundError,
    InvalidDocumentStatusError,
    ValidationError,
)


@pytest.fixture(autouse=True)
def setup_sqlite_tables():
    from app.shared.core.database import Base, engine
    from app.modules.documents.infrastructure.models.picking_wave import PickingWaveModel
    from app.modules.documents.infrastructure.models.cycle_count_sheet import CycleCountSheetModel
    from app.modules.documents.infrastructure.models.carton_package import CartonPackageModel
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)



@pytest.fixture
def wave_service() -> WaveService:
    return WaveService()



@pytest.fixture
def packing_service() -> PackingService:
    return PackingService(tolerance_g=50.0)


# ============================================================================
# Wave Service Tests
# ============================================================================

def test_create_wave(wave_service: WaveService) -> None:
    cutoff = datetime.now(timezone.utc)
    wave = wave_service.create_wave(
        wave_id="WAVE-001",
        carrier="SHOPEE_EXPRESS",
        dispatch_cutoff=cutoff,
        max_orders=50,
    )
    assert wave.wave_id == "WAVE-001"
    assert wave.carrier == "SHOPEE_EXPRESS"
    assert wave.max_orders == 50
    assert wave.status == WaveStatus.DRAFT
    assert len(wave.orders) == 0


def test_wave_capacity_limit_50_orders(wave_service: WaveService) -> None:
    cutoff = datetime.now(timezone.utc)
    wave = wave_service.create_wave(
        wave_id="WAVE-002",
        carrier="GHN",
        dispatch_cutoff=cutoff,
        max_orders=50,
    )

    # Add 50 orders
    for i in range(1, 51):
        order = OutboundOrder(
            order_id=f"ORD-{i:03d}",
            carrier="GHN",
            dispatch_cutoff=cutoff,
            items=[OrderItem(product_id="P1", sku="SKU-1", quantity=2, unit_weight_g=100.0)],
        )
        wave.add_order(order)

    assert len(wave.orders) == 50

    # 51st order must fail
    extra_order = OutboundOrder(
        order_id="ORD-051",
        carrier="GHN",
        dispatch_cutoff=cutoff,
        items=[OrderItem(product_id="P1", sku="SKU-1", quantity=1, unit_weight_g=100.0)],
    )

    with pytest.raises(BusinessRuleViolationError, match="Wave capacity reached"):
        wave.add_order(extra_order)


def test_wave_carrier_mismatch(wave_service: WaveService) -> None:
    cutoff = datetime.now(timezone.utc)
    wave = wave_service.create_wave(
        wave_id="WAVE-003",
        carrier="NINJAVAN",
        dispatch_cutoff=cutoff,
    )

    wrong_carrier_order = OutboundOrder(
        order_id="ORD-999",
        carrier="VIETTEL_POST",
        dispatch_cutoff=cutoff,
        items=[OrderItem(product_id="P1", sku="SKU-1", quantity=1, unit_weight_g=100.0)],
    )

    with pytest.raises(BusinessRuleViolationError, match="does not match wave carrier"):
        wave.add_order(wrong_carrier_order)


def test_plan_wave_by_carrier(wave_service: WaveService) -> None:
    cutoff = datetime.now(timezone.utc)
    candidates = []

    # 55 GHN orders and 10 J&T orders
    for i in range(1, 56):
        candidates.append(
            OutboundOrder(
                order_id=f"GHN-{i:03d}",
                carrier="GHN",
                dispatch_cutoff=cutoff,
                items=[OrderItem(product_id="P1", sku="SKU-1", quantity=1, unit_weight_g=200.0)],
            )
        )
    for i in range(1, 11):
        candidates.append(
            OutboundOrder(
                order_id=f"JT-{i:03d}",
                carrier="J&T",
                dispatch_cutoff=cutoff,
                items=[OrderItem(product_id="P2", sku="SKU-2", quantity=1, unit_weight_g=300.0)],
            )
        )

    wave = wave_service.plan_wave_by_carrier(
        wave_id="WAVE-GHN-01",
        carrier="GHN",
        dispatch_cutoff=cutoff,
        candidate_orders=candidates,
        max_orders=50,
    )

    assert wave.wave_id == "WAVE-GHN-01"
    assert len(wave.orders) == 50
    assert wave.status == WaveStatus.PLANNED
    assert all(o.carrier == "GHN" for o in wave.orders)


def test_batch_picking_task_consolidation(wave_service: WaveService) -> None:
    cutoff = datetime.now(timezone.utc)
    wave = wave_service.create_wave("WAVE-BATCH-01", "SPX", cutoff)

    # Order 1: 3x P1 at A-01-01, 2x P2 at B-02-01
    order1 = OutboundOrder(
        order_id="ORD-101",
        carrier="SPX",
        dispatch_cutoff=cutoff,
        items=[
            OrderItem(product_id="P1", sku="SKU-1", quantity=3, unit_weight_g=500.0, location_id="A-01-01"),
            OrderItem(product_id="P2", sku="SKU-2", quantity=2, unit_weight_g=100.0, location_id="B-02-01"),
        ],
    )
    # Order 2: 5x P1 at A-01-01, 1x P3 at C-03-01
    order2 = OutboundOrder(
        order_id="ORD-102",
        carrier="SPX",
        dispatch_cutoff=cutoff,
        items=[
            OrderItem(product_id="P1", sku="SKU-1", quantity=5, unit_weight_g=500.0, location_id="A-01-01"),
            OrderItem(product_id="P3", sku="SKU-3", quantity=1, unit_weight_g=250.0, location_id="C-03-01"),
        ],
    )

    wave.add_order(order1)
    wave.add_order(order2)

    tasks = wave_service.release_wave("WAVE-BATCH-01")

    # Should consolidate P1 at A-01-01 to 8 units (3+5)
    assert len(tasks) == 3
    p1_task = next(t for t in tasks if t.product_id == "P1")
    assert p1_task.total_quantity == 8
    assert p1_task.location_id == "A-01-01"
    assert wave.status == WaveStatus.RELEASED


def test_wave_picking_lifecycle(wave_service: WaveService) -> None:
    cutoff = datetime.now(timezone.utc)
    wave = wave_service.create_wave("WAVE-LIFE", "NINJAVAN", cutoff)

    order = OutboundOrder(
        order_id="ORD-LIFE-1",
        carrier="NINJAVAN",
        dispatch_cutoff=cutoff,
        items=[OrderItem(product_id="P1", sku="SKU-1", quantity=10, unit_weight_g=100.0, location_id="LOC-1")],
    )
    wave.add_order(order)
    tasks = wave_service.release_wave("WAVE-LIFE")
    task_id = tasks[0].task_id

    # Pick 5 units -> IN_PROGRESS
    task = wave_service.mark_task_picked("WAVE-LIFE", task_id, 5)
    assert task.picked_quantity == 5
    assert task.status == "IN_PROGRESS"
    assert wave.status == WaveStatus.IN_PICKING

    # Pick remaining 5 units -> COMPLETED
    task = wave_service.mark_task_picked("WAVE-LIFE", task_id, 5)
    assert task.picked_quantity == 10
    assert task.status == "COMPLETED"

    # Complete wave
    completed_wave = wave_service.complete_wave("WAVE-LIFE")
    assert completed_wave.status == WaveStatus.COMPLETED
    assert order.status == "PICKED"


# ============================================================================
# Packing Service Tests (Check-Weigher Verification)
# ============================================================================

def test_create_carton_and_theoretical_weight(packing_service: PackingService) -> None:
    carton = packing_service.create_carton(
        carton_id="CTN-001",
        order_id="ORD-101",
        items=[
            PackItem(product_id="P1", sku="SKU-1", quantity=2, unit_weight_g=500.0),  # 1000g
            PackItem(product_id="P2", sku="SKU-2", quantity=1, unit_weight_g=300.0),  # 300g
        ],
        packaging_tare_weight_g=150.0,  # box weight: 150g
    )

    # Net weight = 1300g, Gross theoretical = 1450g
    assert carton.items_weight_g == 1300.0
    assert carton.theoretical_weight_g == 1450.0
    assert carton.status == PackingStatus.PACKING


def test_check_weigher_pass_within_50g(packing_service: PackingService) -> None:
    packing_service.create_carton(
        carton_id="CTN-002",
        order_id="ORD-102",
        items=[PackItem(product_id="P1", sku="SKU-1", quantity=1, unit_weight_g=1000.0)],
        packaging_tare_weight_g=100.0,
    )
    # Theoretical = 1100g

    # Test 1: Exact weight (1100g) -> Pass
    res1 = packing_service.verify_check_weigher("CTN-002", measured_weight_g=1100.0)
    assert res1.is_valid is True
    assert res1.deviation_g == 0.0

    # Test 2: Deviation of +45g (1145g) -> Pass (within <= 50g tolerance)
    res2 = packing_service.verify_check_weigher("CTN-002", measured_weight_g=1145.0)
    assert res2.is_valid is True
    assert res2.deviation_g == 45.0
    assert "PASSED" in res2.message

    # Test 3: Deviation of -30g (1070g) -> Pass
    res3 = packing_service.verify_check_weigher("CTN-002", measured_weight_g=1070.0)
    assert res3.is_valid is True
    assert res3.deviation_g == 30.0

    # Finalize packing
    carton = packing_service.finalize_packing("CTN-002", measured_weight_g=1120.0)
    assert carton.status == PackingStatus.PACKED


def test_check_weigher_fail_over_50g_alert(packing_service: PackingService) -> None:
    packing_service.create_carton(
        carton_id="CTN-003",
        order_id="ORD-103",
        items=[PackItem(product_id="P1", sku="SKU-1", quantity=2, unit_weight_g=400.0)],
        packaging_tare_weight_g=100.0,
    )
    # Theoretical = 900g

    # Measured = 960g -> Deviation = 60g (> 50g tolerance threshold)
    res = packing_service.verify_check_weigher("CTN-003", measured_weight_g=960.0)
    assert res.is_valid is False
    assert res.deviation_g == 60.0
    assert "ALERT: Weight verification FAILED!" in res.message
    assert "exceeds allowed limit (50.0g)" in res.message

    carton = packing_service.get_carton("CTN-003")
    assert carton.status == PackingStatus.WEIGHT_FAILED

    # Finalize packing with strict check should raise BusinessRuleViolationError
    with pytest.raises(BusinessRuleViolationError, match="Packing rejected"):
        packing_service.finalize_packing("CTN-003", measured_weight_g=960.0, strict_check=True)


def test_invalid_measured_weight_validation(packing_service: PackingService) -> None:
    packing_service.create_carton(
        carton_id="CTN-004",
        order_id="ORD-104",
        items=[PackItem(product_id="P1", sku="SKU-1", quantity=1, unit_weight_g=100.0)],
    )

    with pytest.raises(ValidationError, match="must be positive"):
        packing_service.verify_check_weigher("CTN-004", measured_weight_g=0.0)


def test_wave_survives_service_restart(test_session) -> None:
    """Verify PickingWave state persists in database across service restarts."""
    service1 = WaveService(session=test_session)
    cutoff = datetime.now(timezone.utc)
    wave1 = service1.create_wave(
        wave_id="WAVE-RESTART-01",
        carrier="SHOPEE_EXPRESS",
        dispatch_cutoff=cutoff,
    )
    order = OutboundOrder(
        order_id="ORD-RS-1",
        carrier="SHOPEE_EXPRESS",
        dispatch_cutoff=cutoff,
        items=[OrderItem(product_id="P1", sku="SKU-1", quantity=5, unit_weight_g=100.0)],
    )
    wave1.add_order(order)
    service1.release_wave("WAVE-RESTART-01")

    # Simulate service restart: instantiate NEW WaveService instance
    service2 = WaveService(session=test_session)
    wave2 = service2.get_wave("WAVE-RESTART-01")
    assert wave2.wave_id == "WAVE-RESTART-01"
    assert wave2.carrier == "SHOPEE_EXPRESS"
    assert wave2.status == WaveStatus.RELEASED
    assert len(wave2.orders) == 1
    assert wave2.orders[0].order_id == "ORD-RS-1"
    assert len(wave2.picking_tasks) == 1
    assert wave2.picking_tasks[0].total_quantity == 5


def test_packing_survives_service_restart(test_session) -> None:
    """Verify CartonPackage state persists in database across service restarts."""
    service1 = PackingService(session=test_session)
    service1.create_carton(
        carton_id="CTN-RESTART-01",
        order_id="ORD-RS-01",
        items=[PackItem(product_id="P1", sku="SKU-1", quantity=2, unit_weight_g=500.0)],
        packaging_tare_weight_g=100.0,
    )
    service1.verify_check_weigher("CTN-RESTART-01", measured_weight_g=1100.0)

    # Simulate service restart: instantiate NEW PackingService instance
    service2 = PackingService(session=test_session)
    carton2 = service2.get_carton("CTN-RESTART-01")
    assert carton2.carton_id == "CTN-RESTART-01"
    assert carton2.order_id == "ORD-RS-01"
    assert carton2.status == PackingStatus.WEIGHT_VERIFIED
    assert carton2.measured_weight_g == 1100.0
    assert carton2.verification_result is not None
    assert carton2.verification_result.is_valid is True

