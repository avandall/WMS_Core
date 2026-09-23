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

    assert "Reservation only supported for SALE, EXPORT, and TRANSFER" in str(exc_info.value)


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



