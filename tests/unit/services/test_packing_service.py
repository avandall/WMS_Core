"""Unit tests for Carton-Item Manifest & GS1/SSCC Packing Service (TASK-090)."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.shared.core.database import Base, import_all_models
from app.modules.documents.application.services.packing_service import (
    CartonManifestItem,
    CartonPackage,
    PackingService,
    PackingStatus,
)
from app.modules.documents.infrastructure.models.document import DocumentModel
from app.modules.documents.infrastructure.models.document_item import DocumentItemModel
from app.modules.documents.infrastructure.models.carton_package import (
    CartonManifestItemModel,
    CartonPackageModel,
)
from app.modules.documents.infrastructure.repositories.carton_package_repo import (
    PackingRepository,
)
from app.shared.domain.business_exceptions import (
    BusinessRuleViolationError,
    InvalidQuantityError,
    ValidationError,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    import_all_models()
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def packing_service(db_session) -> PackingService:
    repo = PackingRepository(db_session, auto_commit=True)
    return PackingService(repo=repo, tolerance_g=50.0)


def test_carton_manifest_table_schema_and_relational_link(db_session):
    """AC1: Bổ sung bảng quan hệ carton_manifest_items liên kết thùng carton với chi tiết mặt hàng."""
    carton = CartonPackageModel(
        carton_id="SSCC-TEST-001",
        order_id="1001",
        packaging_tare_weight_g=150.0,
        status="PACKING",
    )
    db_session.add(carton)
    db_session.flush()

    item = CartonManifestItemModel(
        carton_id="SSCC-TEST-001",
        package_id="SSCC-TEST-001",
        document_id=1001,
        product_id=501,
        sku="SKU-PHONE-X",
        quantity=3,
        lot_number="LOT-2026-09",
        unit_weight_g=200.0,
    )
    db_session.add(item)
    db_session.commit()

    # Query back via relationship
    reloaded_carton = db_session.get(CartonPackageModel, "SSCC-TEST-001")
    assert reloaded_carton is not None
    assert len(reloaded_carton.manifest_items) == 1
    m_item = reloaded_carton.manifest_items[0]
    assert m_item.product_id == 501
    assert m_item.quantity == 3
    assert m_item.lot_number == "LOT-2026-09"
    assert m_item.document_id == 1001


def test_pack_items_to_cartons_c1_and_c2(packing_service: PackingService, db_session):
    """AC3: Viết test đóng gói 2 sản phẩm vào thùng C1, 1 sản phẩm vào thùng C2 và truy vấn manifest từng thùng chính xác."""
    # 1. Setup Document with Export Requirements:
    # Product 101: 2 units
    # Product 102: 1 unit
    doc = DocumentModel(
        document_id=5001,
        doc_type="SALE",
        status="APPROVED",
        from_warehouse_id=1,
        created_by="pack_operator",
    )
    db_session.add(doc)
    db_session.flush()

    item1 = DocumentItemModel(
        document_id=5001,
        product_id=101,
        quantity=2,
        unit_price=15.0,
        lot_number="LOT-101",
    )
    item2 = DocumentItemModel(
        document_id=5001,
        product_id=102,
        quantity=1,
        unit_price=30.0,
        lot_number="LOT-102",
    )
    db_session.add_all([item1, item2])
    db_session.commit()

    # 2. Pack 2 units of Product 101 into Carton C1
    carton_c1 = packing_service.pack_items_to_carton(
        document_id=5001,
        carton_code="C1",
        items_list=[
            {
                "product_id": 101,
                "quantity": 2,
                "sku": "SKU-PROD-101",
                "lot_number": "LOT-101",
                "unit_weight_g": 250.0,
            }
        ],
        packaging_tare_weight_g=100.0,
    )
    assert carton_c1.carton_id == "C1"

    # 3. Pack 1 unit of Product 102 into Carton C2
    carton_c2 = packing_service.pack_items_to_carton(
        document_id=5001,
        carton_code="C2",
        items_list=[
            {
                "product_id": 102,
                "quantity": 1,
                "sku": "SKU-PROD-102",
                "lot_number": "LOT-102",
                "unit_weight_g": 400.0,
            }
        ],
        packaging_tare_weight_g=120.0,
    )
    assert carton_c2.carton_id == "C2"

    # 4. Verify Manifest for Carton C1
    c1_manifest = packing_service.get_carton_manifest("C1")
    assert len(c1_manifest) == 1
    assert c1_manifest[0].carton_id == "C1"
    assert c1_manifest[0].product_id == 101
    assert c1_manifest[0].quantity == 2
    assert c1_manifest[0].sku == "SKU-PROD-101"
    assert c1_manifest[0].lot_number == "LOT-101"

    # 5. Verify Manifest for Carton C2
    c2_manifest = packing_service.get_carton_manifest("C2")
    assert len(c2_manifest) == 1
    assert c2_manifest[0].carton_id == "C2"
    assert c2_manifest[0].product_id == 102
    assert c2_manifest[0].quantity == 1
    assert c2_manifest[0].sku == "SKU-PROD-102"
    assert c2_manifest[0].lot_number == "LOT-102"

    # 6. Verify Manifest breakdown across whole document
    doc_manifest = packing_service.get_manifest_by_document(5001)
    assert len(doc_manifest) == 2
    carton_map = {m.carton_id: m for m in doc_manifest}
    assert carton_map["C1"].product_id == 101
    assert carton_map["C2"].product_id == 102

    # 7. Verify Detailed Manifest query API
    c1_details = packing_service.get_carton_manifest_details("C1")
    assert c1_details["carton_id"] == "C1"
    assert c1_details["order_id"] == "5001"
    assert c1_details["items_count"] == 1
    assert c1_details["theoretical_weight_g"] == 2 * 250.0 + 100.0  # 600.0g


def test_pack_items_exceeding_document_quantity_raises(packing_service: PackingService, db_session):
    """AC2: Đối soát tổng số lượng không vượt quá số lượng cần xuất trong chứng từ."""
    doc = DocumentModel(
        document_id=7001,
        doc_type="SALE",
        status="APPROVED",
        from_warehouse_id=1,
        created_by="pack_operator",
    )
    db_session.add(doc)
    db_session.flush()

    # Document requires strictly 2 units of product 201
    item = DocumentItemModel(
        document_id=7001,
        product_id=201,
        quantity=2,
        unit_price=50.0,
    )
    db_session.add(item)
    db_session.commit()

    # Step 1: Pack 2 units into Carton C1 -> Succeeds (2/2 packed)
    packing_service.pack_items_to_carton(
        document_id=7001,
        carton_code="BOX-01",
        items_list=[{"product_id": 201, "quantity": 2, "unit_weight_g": 100.0}],
    )

    # Step 2: Attempt to pack 1 more unit into Carton C2 -> Exceeds document limit (3/2)
    with pytest.raises(BusinessRuleViolationError) as exc_info:
        packing_service.pack_items_to_carton(
            document_id=7001,
            carton_code="BOX-02",
            items_list=[{"product_id": 201, "quantity": 1, "unit_weight_g": 100.0}],
        )
    assert "already packed 2/2" in str(exc_info.value)


def test_pack_product_not_in_document_raises(packing_service: PackingService, db_session):
    """Pack item not present in document export requirements raises BusinessRuleViolationError."""
    doc = DocumentModel(
        document_id=8001,
        doc_type="SALE",
        status="APPROVED",
        from_warehouse_id=1,
        created_by="operator",
    )
    db_session.add(doc)
    db_session.flush()

    item = DocumentItemModel(
        document_id=8001,
        product_id=301,
        quantity=5,
        unit_price=10.0,
    )
    db_session.add(item)
    db_session.commit()

    # Attempt to pack product 999 which is not in document 8001
    with pytest.raises(BusinessRuleViolationError) as exc_info:
        packing_service.pack_items_to_carton(
            document_id=8001,
            carton_code="BOX-INV",
            items_list=[{"product_id": 999, "quantity": 1}],
        )
    assert "not present in document 8001" in str(exc_info.value)


def test_pack_items_input_validations(packing_service: PackingService):
    """Input validation tests for empty carton code, negative quantity, empty items list."""
    with pytest.raises(ValidationError):
        packing_service.pack_items_to_carton(document_id=9001, carton_code="", items_list=[{"product_id": 1, "quantity": 1}])

    with pytest.raises(ValidationError):
        packing_service.pack_items_to_carton(document_id=9001, carton_code="C1", items_list=[])

    with pytest.raises(InvalidQuantityError):
        packing_service.pack_items_to_carton(
            document_id=9001,
            carton_code="C1",
            items_list=[{"product_id": 1, "quantity": -5}],
        )


def test_pack_items_with_weight_verification_integration(packing_service: PackingService):
    """Pack items into carton, calculate theoretical weight, and run electronic check-weigher verification."""
    carton = packing_service.pack_items_to_carton(
        document_id=9002,
        carton_code="SSCC-WEIGHT-01",
        items_list=[
            {"product_id": 401, "sku": "SKU-W1", "quantity": 2, "unit_weight_g": 300.0},
            {"product_id": 402, "sku": "SKU-W2", "quantity": 1, "unit_weight_g": 400.0},
        ],
        packaging_tare_weight_g=100.0,
    )

    # Theoretical weight: (2 * 300) + (1 * 400) + 100 = 1100.0g
    assert carton.theoretical_weight_g == 1100.0

    # Scale reads 1120g (deviation = 20g <= 50g tolerance) -> Pass
    res = packing_service.verify_check_weigher("SSCC-WEIGHT-01", measured_weight_g=1120.0)
    assert res.is_valid is True
    assert res.deviation_g == 20.0

    # Finalize packing
    final_carton = packing_service.finalize_packing("SSCC-WEIGHT-01", measured_weight_g=1120.0)
    assert final_carton.status == PackingStatus.PACKED


def test_pack_items_carton_cross_order_isolation_raises(packing_service: PackingService):
    """TASK-097: Scanning a carton already bound to another order_id raises BusinessRuleViolationError."""
    # 1. Pack items for Order 1001 into BOX-ISOLATION-01
    carton_1 = packing_service.pack_items_to_carton(
        document_id=1001,
        carton_code="BOX-ISOLATION-01",
        items_list=[
            {"product_id": 501, "sku": "SKU-501", "quantity": 3, "unit_weight_g": 100.0},
        ],
    )
    assert carton_1.order_id == "1001"
    assert len(carton_1.manifest_items) == 1

    # 2. Packing items for Order 1002 into the SAME carton must be rejected
    with pytest.raises(BusinessRuleViolationError) as exc_info:
        packing_service.pack_items_to_carton(
            document_id=1002,
            carton_code="BOX-ISOLATION-01",
            items_list=[
                {"product_id": 502, "sku": "SKU-502", "quantity": 1, "unit_weight_g": 200.0},
            ],
        )

    assert "already assigned to order '1001'" in str(exc_info.value)
    assert "Cannot mix items from order '1002'" in str(exc_info.value)

    # 3. Verify carton remains unpolluted (only contains Order 1001 items)
    details = packing_service.get_carton_manifest_details("BOX-ISOLATION-01")
    assert details["order_id"] == "1001"
    assert details["items_count"] == 1
    assert details["manifest_items"][0]["product_id"] == 501


def test_suggest_packing_box_native_3d_bpp(packing_service: PackingService):
    """TASK-100 / ARCH-01: Verifies native 3D-BPP carton box suggestion inside PackingService."""
    items = [
        {"sku_code": "LAP-001", "name": "Laptop", "quantity": 1, "length": 30.0, "width": 20.0, "height": 3.0, "weight": 2.0, "allow_rotation": True},
        {"sku_code": "MOU-001", "name": "Mouse", "quantity": 1, "length": 10.0, "width": 6.0, "height": 4.0, "weight": 0.2, "allow_rotation": True},
    ]

    result = packing_service.suggest_packing_box(items=items)
    assert result["success"] is True
    assert result["selected_box"] is not None
    assert result["selected_box"]["box_id"] in ["BOX-S", "BOX-M", "BOX-L", "BOX-XL"]
    assert len(result["recommendations"]) > 0


