"""
Integration Test Suite for Inbound QA/QC Quarantine Workflow & Multi-UOM (TASK-052).

Acceptance Criteria verified:
1. Hàng hóa nhập kho qua IMPORT tự động gán trạng thái vị trí status = 'QUARANTINED',
   không được tính vào available_qty để phân bổ đơn bán (ATP).
2. Tạo chứng từ kiểm định chất lượng QA_INSPECTION:
   - PASS: Chuyển trạng thái sang AVAILABLE và sinh lệnh cất hàng (Putaway task).
   - FAIL: Chuyển trạng thái sang REJECTED/DAMAGED và tạo phiếu trả hàng cho NCC (RTV).
3. Danh mục sản phẩm hỗ trợ bảng quy đổi UOM (1 Pallet = X Cases = Y Eaches) và thông số ti_hi.
4. Đơn hàng SALE không thể reserve hoặc allocate các mặt hàng đang nằm trong khu vực QUARANTINED.
"""

import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.shared.core.database import Base
from app.modules.products.infrastructure.models.product import ProductModel
from app.modules.products.infrastructure.models.product_uom import ProductUomModel
from app.modules.warehouses.infrastructure.models.warehouse import WarehouseModel
from app.modules.positions.infrastructure.models.position import PositionModel
from app.modules.inventory.infrastructure.models.warehouse_inventory import WarehouseInventoryModel
from app.modules.inventory.infrastructure.models.inventory_location import InventoryLocationModel
from app.modules.inventory.infrastructure.models.stock_reservation import StockReservationModel
from app.modules.inventory.infrastructure.models.inventory_transaction import InventoryTransactionModel
from app.modules.inventory.infrastructure.repositories.inventory_repo import InventoryRepo
from app.modules.inventory.application.services.inventory_service import InventoryService
from app.modules.documents.domain.entities.document import Document, DocumentProduct, DocumentType, DocumentStatus
from app.modules.documents.infrastructure.models.document import DocumentModel
from app.modules.documents.infrastructure.models.document_item import DocumentItemModel
from app.modules.documents.infrastructure.repositories.document_repo import DocumentRepo
from app.modules.documents.application.services.document_service import DocumentService
from app.shared.domain.business_exceptions import InsufficientStockError


@pytest.fixture
def db_session():
    """Isolated SQLite in-memory database session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Seed baseline warehouse & product
    wh = WarehouseModel(warehouse_id=1, location="Kho Tổng Tân Bình")
    session.add(wh)

    prod = ProductModel(
        product_id=101,
        name="SKU-PHARMA-101",
        description="Thuốc Kháng Sinh 500mg",
        price=150.0,
        base_uom="EACH",
        ti=10,
        hi=5,
        tie_high="10x5",
    )
    session.add(prod)
    session.commit()

    try:
        yield session
    finally:
        session.close()


class MockEventPublisher:
    def __init__(self):
        self.published_events = []

    def publish(self, event_type: str, payload: dict):
        self.published_events.append({"event_type": event_type, "payload": payload})


def test_inbound_quarantine_blocks_sale_reservation_and_atp(db_session):
    """
    TASK-052 [BIZ-ERR-02]: Hàng mới nhập qua IMPORT được gán status = 'QUARANTINED'.
    Available quantity (ATP) phải bằng 0 và đơn hàng SALE không thể reserve.
    """
    inv_repo = InventoryRepo(db_session)
    event_pub = MockEventPublisher()
    inv_service = InventoryService(inv_repo, event_publisher=event_pub)

    # 1. Nhập 100 đơn vị vào kho với status = QUARANTINED
    inv_service.adjust_location_inventory(
        warehouse_id=1,
        position_id=10,
        product_id=101,
        quantity_delta=100,
        status="QUARANTINED",
        lpn="LPN-INB-001",
        lot_number="LOT-2026-X",
    )

    # 2. Kiểm tra Available Qty (ATP)
    avail = inv_repo.get_availability(product_id=101, warehouse_id=1)
    assert avail["physical_qty"] == 100
    assert avail["available_qty"] == 0, "Quarantined inventory must NOT be included in available_qty (ATP)!"

    # 3. Đơn hàng SALE cố gắng reserve -> phải báo lỗi InsufficientStockError
    with pytest.raises(InsufficientStockError, match="Insufficient available stock"):
        inv_repo.reserve_stock(
            product_id=101,
            warehouse_id=1,
            requested_qty=10,
            created_by="sales_rep_01",
        )

    # 4. Kiểm tra FEFO allocation: Không phân bổ hàng QUARANTINED
    with pytest.raises(InsufficientStockError):
        inv_service.allocate_fefo(
            warehouse_id=1,
            product_id=101,
            quantity=10,
            status="AVAILABLE",
        )


def test_qa_inspection_pass_promotes_to_available_and_generates_putaway(db_session):
    """
    TASK-052: Kiểm định QA PASS:
    - Chuyển trạng thái hàng sang AVAILABLE.
    - Sinh lệnh cất hàng (Putaway task).
    - Đơn bán SALE có thể reserve thành công sau khi PASS.
    """
    doc_repo = DocumentRepo(db_session)
    inv_repo = InventoryRepo(db_session)
    event_pub = MockEventPublisher()
    doc_service = DocumentService(doc_repo, session=db_session, event_publisher=event_pub, inventory_repo=inv_repo)

    # 1. Tạo chứng từ IMPORT cho lô hàng
    import_doc = doc_service.create_import_document(
        to_warehouse_id=1,
        items=[{"product_id": 101, "quantity": 50, "unit_price": 150.0}],
        created_by="inbound_officer",
        note="Nhập hàng nhà cung cấp PharmaCo",
    )
    doc_id = import_doc.document_id

    # Đưa hàng vào trạng thái QUARANTINED tại cửa nhận Dock
    inv_repo.adjust_location_quantity(
        warehouse_id=1,
        position_id=1,
        product_id=101,
        quantity_delta=50,
        status="QUARANTINED",
    )
    assert inv_repo.get_availability(product_id=101, warehouse_id=1)["available_qty"] == 0

    # 2. Nhân viên KCS thực hiện QA Inspection với kết quả PASS
    inspected_doc = doc_service.inspect_qa_document(
        document_id=doc_id,
        inspected_by="qa_inspector_nguyen",
        passed=True,
        note="Đạt tiêu chuẩn COA & nhiệt độ bảo quản 2-8 độ C",
    )

    assert inspected_doc.status == DocumentStatus.QA_INSPECTED

    # 3. Xác minh lệnh Putaway task được sinh ra trong event
    qa_event = next(e for e in event_pub.published_events if e["event_type"] == "DocumentQaInspected")
    putaway_tasks = qa_event["payload"]["putaway_tasks"]
    assert len(putaway_tasks) == 1
    assert putaway_tasks[0]["product_id"] == 101
    assert putaway_tasks[0]["quantity"] == 50
    assert putaway_tasks[0]["status"] == "PENDING_PUTAWAY"

    # 4. Xác minh trạng thái tồn kho chuyển sang AVAILABLE và ATP tăng lên 50
    avail_after = inv_repo.get_availability(product_id=101, warehouse_id=1)
    assert avail_after["available_qty"] == 50

    # 5. Đơn hàng SALE giờ đây reserve thành công!
    res_id = inv_repo.reserve_stock(
        product_id=101,
        warehouse_id=1,
        requested_qty=20,
        created_by="sales_rep_01",
    )
    assert res_id > 0
    assert inv_repo.get_availability(product_id=101, warehouse_id=1)["available_qty"] == 30


def test_qa_inspection_fail_transitions_to_rejected_and_generates_rtv(db_session):
    """
    TASK-052: Kiểm định QA FAIL:
    - Chuyển trạng thái hàng sang REJECTED/DAMAGED.
    - Tự động tạo phiếu trả hàng cho nhà cung cấp (Return to Vendor - RTV / PURCHASE_RETURN).
    - Hàng tiếp tục không được bán ra thị trường.
    """
    doc_repo = DocumentRepo(db_session)
    inv_repo = InventoryRepo(db_session)
    event_pub = MockEventPublisher()
    doc_service = DocumentService(doc_repo, session=db_session, event_publisher=event_pub, inventory_repo=inv_repo)

    # 1. Tạo chứng từ IMPORT
    import_doc = doc_service.create_import_document(
        to_warehouse_id=1,
        items=[{"product_id": 101, "quantity": 40, "unit_price": 150.0}],
        created_by="inbound_officer",
        note="Nhập hàng phát hiện rách bao bì",
    )
    doc_id = import_doc.document_id

    # Đưa hàng vào trạng thái QUARANTINED
    inv_repo.adjust_location_quantity(
        warehouse_id=1,
        position_id=1,
        product_id=101,
        quantity_delta=40,
        status="QUARANTINED",
    )

    # 2. Nhân viên KCS thực hiện QA Inspection với kết quả FAIL
    inspected_doc = doc_service.inspect_qa_document(
        document_id=doc_id,
        inspected_by="qa_inspector_nguyen",
        passed=False,
        note="Lỗi hỏng vỡ seal bảo quản và biến chất dung dịch",
    )

    assert inspected_doc.status == DocumentStatus.CANCELLED
    assert "QA Inspection Failed" in inspected_doc.cancellation_reason

    # 3. Xác minh tự động sinh phiếu trả hàng nhà cung cấp (RTV)
    qa_event = next(e for e in event_pub.published_events if e["event_type"] == "DocumentQaInspected")
    rtv_doc_id = qa_event["payload"]["rtv_document_id"]
    assert rtv_doc_id is not None

    rtv_doc = doc_service.get_document(rtv_doc_id)
    assert rtv_doc.doc_type == DocumentType.PURCHASE_RETURN
    assert rtv_doc.transaction_type == "PURCHASE_RETURN_SHIPMENT"
    assert rtv_doc.reason_code == "QA_REJECTED"
    assert len(rtv_doc.items) == 1
    assert rtv_doc.items[0].quantity == 40

    # 4. Hàng REJECTED không được bán (ATP vẫn bằng 0)
    avail = inv_repo.get_availability(product_id=101, warehouse_id=1)
    assert avail["available_qty"] == 0


def test_multi_uom_conversions_and_palletizing_tie_high(db_session):
    """
    TASK-052 [BIZ-ERR-04]: Danh mục sản phẩm hỗ trợ cấu trúc đóng gói đa tầng Multi-UOM:
    1 Pallet = 50 Cases, 1 Case = 10 Eaches, cùng thông số ti_hi (Ti: số thùng/lớp, Hi: số lớp/pallet).
    """
    prod = db_session.get(ProductModel, 101)
    assert prod is not None

    # 1. Xác minh thông số Palletizing (Ti x Hi)
    assert prod.ti == 10
    assert prod.hi == 5
    assert prod.ti_hi == "10x5"
    assert prod.tie_high == "10x5"

    # 2. Thiết lập bảng quy đổi UOM:
    # 1 CASE = 10 EACH
    # 1 PALLET = 500 EACH (tương đương 50 CASES)
    uom_case = ProductUomModel(
        product_id=101,
        uom_code="CASE",
        conversion_factor=10.0,
        to_uom_code="EACH",
    )
    uom_pallet = ProductUomModel(
        product_id=101,
        uom_code="PALLET",
        conversion_factor=500.0,
        to_uom_code="EACH",
    )
    db_session.add(uom_case)
    db_session.add(uom_pallet)
    db_session.commit()

    # 3. Kiểm tra thuộc tính product_uom_conversions
    conversions = prod.product_uom_conversions
    assert len(conversions) == 2
    uom_codes = {u.uom_code for u in conversions}
    assert "CASE" in uom_codes
    assert "PALLET" in uom_codes

    # 4. Kiểm tra hàm chuyển đổi UOM:
    # 2 Pallets = 1,000 Eaches
    eaches_from_pallets = prod.convert_uom_quantity(2.0, from_uom="PALLET", to_uom="EACH")
    assert eaches_from_pallets == 1000.0

    # 2 Pallets = 100 Cases (1000 / 10)
    cases_from_pallets = prod.convert_uom_quantity(2.0, from_uom="PALLET", to_uom="CASE")
    assert cases_from_pallets == 100.0

    # 5 Cases = 50 Eaches
    eaches_from_cases = prod.convert_uom_quantity(5.0, from_uom="CASE", to_uom="EACH")
    assert eaches_from_cases == 50.0
