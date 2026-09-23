"""
Unit tests for DocumentService — TASK-019
Validates auto-release of stock reservations when cancelling documents in RESERVED / IN_PROGRESS status.
"""

from unittest.mock import MagicMock, patch
import pytest

from app.modules.documents.application.services.document_service import DocumentService
from app.modules.documents.domain.entities.document import (
    Document,
    DocumentProduct,
    DocumentStatus,
    DocumentType,
)
from app.modules.documents.domain.interfaces.document_repo import IDocumentRepo


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
