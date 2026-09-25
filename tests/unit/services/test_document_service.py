import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Purge any previously imported 'app' module to avoid cross-service namespace collisions
for mod in list(sys.modules.keys()):
    if mod == "app" or mod.startswith("app."):
        del sys.modules[mod]

doc_src = str(Path(__file__).resolve().parent.parent.parent.parent / "Services" / "documents-service" / "src")
if doc_src not in sys.path:
    sys.path.insert(0, doc_src)

import pytest

from app.modules.documents.application.services.document_service import DocumentService
from app.modules.documents.domain.entities.document import (
    Document,
    DocumentProduct,
    DocumentStatus,
    DocumentType,
)
from app.modules.documents.domain.exceptions import InvalidDocumentStatusError, DocumentNotFoundError
from app.modules.documents.domain.interfaces.document_repo import IDocumentRepo
from app.shared.domain.business_exceptions import EntityNotFoundError, ValidationError


@pytest.fixture
def mock_document_repo():
    repo = MagicMock(spec=IDocumentRepo)
    repo._store = {}

    def mock_get(doc_id):
        return repo._store.get(doc_id)

    def mock_save(doc):
        repo._store[doc.document_id] = doc

    repo.get.side_effect = mock_get
    repo.save.side_effect = mock_save
    return repo


@pytest.fixture
def document_service(mock_document_repo):
    return DocumentService(document_repo=mock_document_repo)


def test_cancel_reserved_document_releases_reservation(document_service, mock_document_repo):
    """
    TASK-019 Requirement:
    Cancelling a document in RESERVED status auto-releases stock reservations via gRPC ReleaseReservation.
    """
    # 1. Setup Document in RESERVED state with reserved stock
    item = DocumentProduct(product_id=10, quantity=5, unit_price=100.0)
    item.reserved_qty = 5

    doc = Document(
        document_id=1,
        doc_type=DocumentType.SALE,
        from_warehouse_id=1,
        items=[item],
        created_by="sales_rep",
    )
    doc.status = DocumentStatus.RESERVED
    mock_document_repo._store[1] = doc

    # 2. Mock gRPC channel & InventoryServiceStub
    mock_reservation = MagicMock()
    mock_reservation.id = 501
    mock_reservation.document_id = 1
    mock_reservation.status = "RESERVED"

    mock_list_resp = MagicMock()
    mock_list_resp.reservations = [mock_reservation]

    mock_release_resp = MagicMock()
    mock_release_resp.success = True

    mock_stub = MagicMock()
    mock_stub.ListReservations.return_value = mock_list_resp
    mock_stub.ReleaseReservation.return_value = mock_release_resp

    with patch(
        "shared_utils.security.grpc.configured_grpc_channel"
    ) as mock_channel_ctx:
        mock_channel = MagicMock()
        mock_channel_ctx.return_value.__enter__.return_value = mock_channel

        with patch(
            "documents_service.gen.wms.inventory.v1.inventory_pb2_grpc.InventoryServiceStub",
            return_value=mock_stub,
        ):
            # 3. Call cancel_document
            cancelled_doc = document_service.cancel_document(
                document_id=1,
                cancelled_by="manager",
                reason="Order cancelled by customer",
            )

    # 4. Verifications
    # Verify ReleaseReservation gRPC request was made for reservation ID 501
    assert mock_stub.ReleaseReservation.called
    release_req = mock_stub.ReleaseReservation.call_args[0][0]
    assert release_req.reservation_id == 501
    assert release_req.released_qty == 0

    # Verify document status updated to CANCELLED
    assert cancelled_doc.status == DocumentStatus.CANCELLED
    assert cancelled_doc.cancelled_by == "manager"
    assert cancelled_doc.cancellation_reason == "Order cancelled by customer"

    # Verify item reserved_qty reset to 0
    assert cancelled_doc.items[0].reserved_qty == 0


def test_cancel_in_progress_document_releases_reservation(document_service, mock_document_repo):
    """
    TASK-019 Requirement:
    Cancelling a document in IN_PROGRESS status also auto-releases stock reservations.
    """
    item = DocumentProduct(product_id=20, quantity=10, unit_price=50.0)
    item.reserved_qty = 10

    doc = Document(
        document_id=2,
        doc_type=DocumentType.SALE,
        from_warehouse_id=2,
        items=[item],
        created_by="picker",
    )
    doc.status = DocumentStatus.IN_PROGRESS
    mock_document_repo._store[2] = doc

    mock_reservation = MagicMock()
    mock_reservation.id = 702
    mock_reservation.document_id = 2
    mock_reservation.status = "RESERVED"

    mock_list_resp = MagicMock()
    mock_list_resp.reservations = [mock_reservation]

    mock_release_resp = MagicMock()
    mock_release_resp.success = True

    mock_stub = MagicMock()
    mock_stub.ListReservations.return_value = mock_list_resp
    mock_stub.ReleaseReservation.return_value = mock_release_resp

    with patch(
        "shared_utils.security.grpc.configured_grpc_channel"
    ) as mock_channel_ctx:
        mock_channel = MagicMock()
        mock_channel_ctx.return_value.__enter__.return_value = mock_channel

        with patch(
            "documents_service.gen.wms.inventory.v1.inventory_pb2_grpc.InventoryServiceStub",
            return_value=mock_stub,
        ):
            cancelled_doc = document_service.cancel_document(
                document_id=2,
                cancelled_by="admin",
                reason="Stock damage during pick",
            )

    assert mock_stub.ReleaseReservation.called
    assert cancelled_doc.status == DocumentStatus.CANCELLED
    assert cancelled_doc.items[0].reserved_qty == 0


def test_cancel_draft_document_does_not_call_release_reservation(document_service, mock_document_repo):
    """
    Cancelling a DRAFT document without reserved stock should not trigger gRPC release.
    """
    item = DocumentProduct(product_id=30, quantity=5, unit_price=10.0)
    doc = Document(
        document_id=3,
        doc_type=DocumentType.SALE,
        from_warehouse_id=1,
        items=[item],
        created_by="user",
    )
    doc.status = DocumentStatus.DRAFT
    mock_document_repo._store[3] = doc

    with patch(
        "shared_utils.security.grpc.configured_grpc_channel"
    ) as mock_channel_ctx:
        cancelled_doc = document_service.cancel_document(
            document_id=3,
            cancelled_by="user",
            reason="User changed mind",
        )

    assert not mock_channel_ctx.called
    assert cancelled_doc.status == DocumentStatus.CANCELLED


def test_export_reserve_blocks_concurrent_export(document_service, mock_document_repo):
    """
    TASK-023 Requirement:
    Reserving stock for an EXPORT document succeeds and blocks concurrent reservation when stock is insufficient.
    """
    # 1. Setup POSTED Export document
    item = DocumentProduct(product_id=101, quantity=10, unit_price=50.0)
    export_doc = Document(
        document_id=10,
        doc_type=DocumentType.EXPORT,
        from_warehouse_id=1,
        items=[item],
        created_by="exporter",
    )
    export_doc.status = DocumentStatus.POSTED
    mock_document_repo._store[10] = export_doc

    # 2. Setup mock ReserveStock response for first EXPORT
    mock_reserve_resp_1 = MagicMock()
    mock_reserve_resp_1.success = True
    mock_reserve_resp_1.reservation_id = 901

    mock_stub_1 = MagicMock()
    mock_stub_1.ReserveStock.return_value = mock_reserve_resp_1

    with patch("shared_utils.security.grpc.configured_grpc_channel") as mock_channel_ctx:
        mock_channel = MagicMock()
        mock_channel_ctx.return_value.__enter__.return_value = mock_channel
        with patch("documents_service.gen.wms.inventory.v1.inventory_pb2_grpc.InventoryServiceStub", return_value=mock_stub_1):
            reserved_doc = document_service.reserve_request_stock(document_id=10)

    # Verify reservation call parameters
    assert mock_stub_1.ReserveStock.called
    req = mock_stub_1.ReserveStock.call_args[0][0]
    assert req.product_id == 101
    assert req.quantity == 10
    assert req.warehouse_id == 1
    assert req.source_type == "export_document"
    assert reserved_doc.items[0].reserved_qty == 10

    # 3. Concurrent EXPORT attempt when stock is insufficient (ReserveStock fails)
    export_doc_2 = Document(
        document_id=11,
        doc_type=DocumentType.EXPORT,
        from_warehouse_id=1,
        items=[DocumentProduct(product_id=101, quantity=10, unit_price=50.0)],
        created_by="exporter_2",
    )
    export_doc_2.status = DocumentStatus.POSTED
    mock_document_repo._store[11] = export_doc_2

    mock_reserve_resp_2 = MagicMock()
    mock_reserve_resp_2.success = False
    mock_reserve_resp_2.message = "Insufficient available stock"

    mock_stub_2 = MagicMock()
    mock_stub_2.ReserveStock.return_value = mock_reserve_resp_2

    with patch("shared_utils.security.grpc.configured_grpc_channel") as mock_channel_ctx:
        mock_channel = MagicMock()
        mock_channel_ctx.return_value.__enter__.return_value = mock_channel
        with patch("documents_service.gen.wms.inventory.v1.inventory_pb2_grpc.InventoryServiceStub", return_value=mock_stub_2):
            with pytest.raises(ValidationError) as exc_info:
                document_service.reserve_request_stock(document_id=11)
            assert "Insufficient available stock" in str(exc_info.value)


def test_transfer_reserve_success(document_service, mock_document_repo):
    """
    TASK-023 Requirement:
    Reserving stock for a TRANSFER document succeeds using from_warehouse_id.
    """
    item = DocumentProduct(product_id=202, quantity=15, unit_price=30.0)
    transfer_doc = Document(
        document_id=20,
        doc_type=DocumentType.TRANSFER,
        from_warehouse_id=2,
        to_warehouse_id=3,
        items=[item],
        created_by="transfer_agent",
    )
    transfer_doc.status = DocumentStatus.POSTED
    mock_document_repo._store[20] = transfer_doc

    mock_reserve_resp = MagicMock()
    mock_reserve_resp.success = True
    mock_reserve_resp.reservation_id = 902

    mock_stub = MagicMock()
    mock_stub.ReserveStock.return_value = mock_reserve_resp

    with patch("shared_utils.security.grpc.configured_grpc_channel") as mock_channel_ctx:
        mock_channel = MagicMock()
        mock_channel_ctx.return_value.__enter__.return_value = mock_channel
        with patch("documents_service.gen.wms.inventory.v1.inventory_pb2_grpc.InventoryServiceStub", return_value=mock_stub):
            reserved_doc = document_service.reserve_request_stock(document_id=20)

    assert mock_stub.ReserveStock.called
    req = mock_stub.ReserveStock.call_args[0][0]
    assert req.product_id == 202
    assert req.quantity == 15
    assert req.warehouse_id == 2
    assert req.source_type == "transfer_document"
    assert reserved_doc.items[0].reserved_qty == 15


def test_import_reserve_rejected(document_service, mock_document_repo):
    """
    TASK-023 Requirement:
    Attempting to reserve stock for an IMPORT document raises InvalidDocumentStatusError.
    """
    item = DocumentProduct(product_id=303, quantity=100, unit_price=10.0)
    import_doc = Document(
        document_id=30,
        doc_type=DocumentType.IMPORT,
        to_warehouse_id=1,
        items=[item],
        created_by="importer",
    )
    import_doc.status = DocumentStatus.POSTED
    mock_document_repo._store[30] = import_doc

    with pytest.raises(InvalidDocumentStatusError) as exc_info:
        document_service.reserve_request_stock(document_id=30)

    assert "Reservation only supported for SALE, EXPORT, TRANSFER" in str(exc_info.value)


def test_create_document_invalid_product_raises(mock_document_repo):
    """
    TASK-035 Acceptance Criteria [BIZ-20]:
    Creating a document with an invalid/non-existent product_id raises EntityNotFoundError.
    """
    mock_product_repo = MagicMock()
    mock_product_repo.get.return_value = None  # Product 99999 does not exist

    service = DocumentService(
        document_repo=mock_document_repo,
        product_repo=mock_product_repo,
    )

    invalid_items = [
        {"product_id": 99999, "quantity": 10, "unit_price": 50.0}
    ]

    with pytest.raises(EntityNotFoundError) as exc_info:
        service.create_sale_document(
            from_warehouse_id=1,
            items=invalid_items,
            created_by="sales_rep",
        )

    assert "Product 99999 not found" in str(exc_info.value)
    mock_product_repo.get.assert_called_once_with(99999)


def test_get_by_status_uses_sql_filter(document_service, mock_document_repo):
    """
    TASK-038 Requirement:
    get_documents_by_status and get_pending_documents must query document_repo.get_all
    with status SQL filter parameter instead of fetching all documents and filtering in memory.
    """
    mock_doc = Document(
        document_id=100,
        doc_type=DocumentType.SALE,
        from_warehouse_id=1,
        items=[],
        created_by="test_user",
    )
    mock_doc.status = DocumentStatus.DRAFT
    mock_document_repo.get_all.return_value = [mock_doc]

    # Test get_documents_by_status(DRAFT)
    res_status = document_service.get_documents_by_status(DocumentStatus.DRAFT)
    assert res_status == [mock_doc]
    mock_document_repo.get_all.assert_called_with(status=DocumentStatus.DRAFT)

    # Test get_pending_documents()
    mock_document_repo.get_all.reset_mock()
    res_pending = document_service.get_pending_documents()
    assert res_pending == [mock_doc]
    mock_document_repo.get_all.assert_called_with(status=DocumentStatus.DRAFT)


def test_sale_execution_requires_reservation(document_service, mock_document_repo):
    """TASK-042 [FLOW-02]: Sale order execution must enforce reservation before execution."""
    item = DocumentProduct(product_id=1, quantity=10, unit_price=10.0)
    doc = Document(
        document_id=10,
        doc_type=DocumentType.SALE,
        from_warehouse_id=1,
        items=[item],
        created_by="tester",
    )
    doc.status = DocumentStatus.POSTED
    mock_document_repo._store[10] = doc

    with pytest.raises(InvalidDocumentStatusError) as exc_info:
        document_service.start_execution(document_id=10)

    assert "must have active reservation" in str(exc_info.value)


def test_partial_fulfillment_releases_remainder(document_service, mock_document_repo):
    """TASK-042 [EDGE-01]: Partial fulfillment (shipping 80/100) auto-releases surplus reservation."""
    item = DocumentProduct(product_id=1, quantity=100, unit_price=10.0)
    item.reserved_qty = 100
    doc = Document(
        document_id=11,
        doc_type=DocumentType.SALE,
        from_warehouse_id=1,
        items=[item],
        created_by="tester",
    )
    doc.status = DocumentStatus.IN_PROGRESS
    mock_document_repo._store[11] = doc

    executed_doc = document_service.confirm_execution(
        document_id=11,
        items=[{"product_id": 1, "quantity": 80}],
    )

    assert executed_doc.status == DocumentStatus.EXECUTED
    assert executed_doc.items[0].executed_qty == 80
    assert executed_doc.items[0].reserved_qty == 80


def test_reserve_request_stock_sorts_items_by_product_id(document_service, mock_document_repo):
    """
    TASK-081 Acceptance Criteria:
    - Trong DocumentService.reserve_request_stock(), document.items được sắp xếp theo int(item.product_id)
      trước khi gửi gRPC ReserveStock để ngăn chặn Deadlock AB-BA.
    """
    from unittest.mock import MagicMock, patch

    # Items provided in REVERSE order: SKU 300, then SKU 100, then SKU 200
    item1 = DocumentProduct(product_id=300, quantity=5, unit_price=10.0)
    item2 = DocumentProduct(product_id=100, quantity=10, unit_price=20.0)
    item3 = DocumentProduct(product_id=200, quantity=15, unit_price=30.0)

    doc = Document(
        document_id=777,
        doc_type=DocumentType.SALE,
        from_warehouse_id=1,
        items=[item1, item2, item3],
        created_by="tester",
    )
    doc.status = DocumentStatus.POSTED
    mock_document_repo._store[777] = doc

    called_product_ids = []

    def mock_reserve_stock(req, timeout=10):
        called_product_ids.append(req.product_id)
        mock_resp = MagicMock()
        mock_resp.success = True
        mock_resp.reservation_id = 9000 + req.product_id
        return mock_resp

    mock_stub = MagicMock()
    mock_stub.ReserveStock.side_effect = mock_reserve_stock

    with patch("shared_utils.security.grpc.configured_grpc_channel") as mock_channel_ctx:
        mock_channel = MagicMock()
        mock_channel_ctx.return_value.__enter__.return_value = mock_channel
        with patch("documents_service.gen.wms.inventory.v1.inventory_pb2_grpc.InventoryServiceStub", return_value=mock_stub):
            reserved_doc = document_service.reserve_request_stock(document_id=777)

    assert reserved_doc.status == DocumentStatus.RESERVED
    # Verification: gRPC calls must strictly follow sorted order [100, 200, 300]
    assert called_product_ids == [100, 200, 300], f"Expected sorted lock acquisition [100, 200, 300], got {called_product_ids}"


def test_sales_return_initializes_quarantined_stock_and_qa_promotes_to_available(mock_document_repo):
    """
    TASK-083 Acceptance Criteria:
    - Khi tạo chứng từ SALES_RETURN, hệ thống tự động tạo tồn kho với status='QUARANTINED'.
    - Khi inspect_qa_document(passed=True), hệ thống trừ QUARANTINED và cộng AVAILABLE.
    """
    mock_inv_repo = MagicMock()
    mock_session = MagicMock()
    service = DocumentService(
        document_repo=mock_document_repo,
        inventory_repo=mock_inv_repo,
        session=mock_session,
    )

    # 1. Create SALES_RETURN document
    doc = service.create_sales_return_document(
        to_warehouse_id=2,
        items=[{
            "product_id": 501,
            "quantity": 10,
            "unit_price": 45.0,
            "position_id": 15,
            "lot_number": "LOT-RET-501",
            "owner_id": "3PL-CLIENT-A",
        }],
        created_by="receiving_clerk",
        note="Customer return defective batch",
    )

    # Verify Document properties
    assert doc.doc_type == DocumentType.SALES_RETURN
    assert doc.to_warehouse_id == 2
    assert len(doc.items) == 1
    assert doc.items[0].product_id == 501
    assert doc.items[0].quantity == 10

    # Verify inventory was initialized with status='QUARANTINED'
    mock_inv_repo.adjust_location_quantity.assert_called_once_with(
        warehouse_id=2,
        position_id=15,
        product_id=501,
        quantity_delta=10,
        status="QUARANTINED",
        lot_number="LOT-RET-501",
        lpn="",
        owner_id="3PL-CLIENT-A",
    )
    mock_inv_repo.adjust_location_quantity.reset_mock()

    # 2. QA Inspect Passed
    inspected = service.inspect_qa_document(
        document_id=doc.document_id,
        inspected_by="qa_inspector",
        passed=True,
        note="Inspection passed - repackaged",
    )

    assert inspected.status == DocumentStatus.QA_INSPECTED
    # Verify inventory adjusted: -10 QUARANTINED, +10 AVAILABLE
    assert mock_inv_repo.adjust_location_quantity.call_count == 2
    mock_inv_repo.adjust_location_quantity.assert_any_call(
        warehouse_id=2,
        position_id=15,
        product_id=501,
        quantity_delta=-10,
        status="QUARANTINED",
        lot_number="LOT-RET-501",
        lpn="",
        owner_id="3PL-CLIENT-A",
    )
    mock_inv_repo.adjust_location_quantity.assert_any_call(
        warehouse_id=2,
        position_id=15,
        product_id=501,
        quantity_delta=10,
        status="AVAILABLE",
        lot_number="LOT-RET-501",
        lpn="",
        owner_id="3PL-CLIENT-A",
    )


def test_sales_return_qa_inspection_failure_raises_and_rollbacks(mock_document_repo):
    """
    TASK-083 Acceptance Criteria:
    - Trong inspect_qa_document, xóa bỏ khối except Exception: pass.
    - Nếu lỗi xảy ra trong quá trình cập nhật tồn kho, ném lỗi rõ ràng và rollback transaction.
    """
    from app.shared.domain.business_exceptions import InsufficientStockError

    mock_inv_repo = MagicMock()
    mock_session = MagicMock()
    service = DocumentService(
        document_repo=mock_document_repo,
        inventory_repo=mock_inv_repo,
        session=mock_session,
    )

    doc = service.create_sales_return_document(
        to_warehouse_id=1,
        items=[{"product_id": 502, "quantity": 5, "unit_price": 20.0, "position_id": 3}],
        created_by="clerk",
    )

    # Simulate InsufficientStockError during QA inventory promotion
    mock_inv_repo.adjust_location_quantity.side_effect = InsufficientStockError("Quarantined location not found")

    with pytest.raises(InsufficientStockError) as exc_info:
        service.inspect_qa_document(
            document_id=doc.document_id,
            inspected_by="qa_inspector",
            passed=True,
        )

    assert "Quarantined location not found" in str(exc_info.value)
    # Verify rollback was called on failure
    mock_session.rollback.assert_called_once()


def test_sales_return_qa_inspection_rejected_transitions_to_rejected(mock_document_repo):
    """
    TASK-083: Khi QA Failed, QUARANTINED được trừ và REJECTED được cộng.
    """
    mock_inv_repo = MagicMock()
    mock_session = MagicMock()
    service = DocumentService(
        document_repo=mock_document_repo,
        inventory_repo=mock_inv_repo,
        session=mock_session,
    )

    doc = service.create_sales_return_document(
        to_warehouse_id=1,
        items=[{"product_id": 503, "quantity": 8, "unit_price": 30.0, "position_id": 4, "lot_number": "LOT-REJ"}],
        created_by="clerk",
    )
    mock_inv_repo.adjust_location_quantity.reset_mock()

    inspected = service.inspect_qa_document(
        document_id=doc.document_id,
        inspected_by="qa_inspector",
        passed=False,
        note="Item physically broken",
    )

    assert inspected.status == DocumentStatus.CANCELLED
    assert "QA Inspection Failed" in inspected.cancellation_reason
    # Verify inventory was transitioned to REJECTED
    assert mock_inv_repo.adjust_location_quantity.call_count == 2
    mock_inv_repo.adjust_location_quantity.assert_any_call(
        warehouse_id=1,
        position_id=4,
        product_id=503,
        quantity_delta=-8,
        status="QUARANTINED",
        lot_number="LOT-REJ",
        lpn="",
        owner_id="DEFAULT_OWNER",
    )
    mock_inv_repo.adjust_location_quantity.assert_any_call(
        warehouse_id=1,
        position_id=4,
        product_id=503,
        quantity_delta=8,
        status="REJECTED",
        lot_number="LOT-REJ",
        lpn="",
        owner_id="DEFAULT_OWNER",
    )


def test_sales_return_e2e_with_real_inventory_repo(mock_document_repo):
    """
    TASK-083 Acceptance Criteria:
    - Viết test end-to-end: Tạo đơn trả hàng -> QA kiểm định Passed ->
      Tồn kho AVAILABLE tăng chính xác theo số lượng hàng trả về.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.shared.core.database import Base, import_all_models
    from app.modules.inventory.infrastructure.repositories.inventory_repo import InventoryRepo
    from app.modules.inventory.infrastructure.models.inventory_location import InventoryLocationModel

    engine = create_engine("sqlite:///:memory:", echo=False)
    import_all_models()
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    inv_repo = InventoryRepo(session)
    service = DocumentService(
        document_repo=mock_document_repo,
        inventory_repo=inv_repo,
        session=session,
    )

    product_id = 999
    warehouse_id = 1
    position_id = 10
    return_qty = 20

    # 1. Create SALES_RETURN document
    doc = service.create_sales_return_document(
        to_warehouse_id=warehouse_id,
        items=[{
            "product_id": product_id,
            "quantity": return_qty,
            "unit_price": 50.0,
            "position_id": position_id,
            "lot_number": "LOT-RET-REAL",
        }],
        created_by="return_officer",
        note="Customer returning unopened boxes",
    )

    # Check that location has 20 QUARANTINED and 0 AVAILABLE
    quarantined_row = session.query(InventoryLocationModel).filter_by(
        warehouse_id=warehouse_id,
        position_id=position_id,
        product_id=product_id,
        status="QUARANTINED",
    ).first()
    assert quarantined_row is not None
    assert quarantined_row.quantity == 20

    available_before = session.query(InventoryLocationModel).filter_by(
        warehouse_id=warehouse_id,
        position_id=position_id,
        product_id=product_id,
        status="AVAILABLE",
    ).first()
    assert available_before is None or available_before.quantity == 0

    # 2. Perform QA Inspection Passed
    inspected = service.inspect_qa_document(
        document_id=doc.document_id,
        inspected_by="qa_specialist",
        passed=True,
        note="Quality validated - goods pristine",
    )

    assert inspected.status == DocumentStatus.QA_INSPECTED

    # Check that QUARANTINED is now 0 and AVAILABLE is 20!
    session.refresh(quarantined_row)
    assert quarantined_row.quantity == 0

    available_after = session.query(InventoryLocationModel).filter_by(
        warehouse_id=warehouse_id,
        position_id=position_id,
        product_id=product_id,
        status="AVAILABLE",
    ).first()
    assert available_after is not None
    assert available_after.quantity == return_qty
    session.close()





