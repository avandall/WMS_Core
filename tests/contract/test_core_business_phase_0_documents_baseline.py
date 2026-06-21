from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest


ROOT_DIR = Path(__file__).resolve().parents[2]
DOCUMENTS_SRC = ROOT_DIR / "Services/documents-service/src"
sys.path.insert(0, str(DOCUMENTS_SRC))
for module_name in list(sys.modules):
    if module_name == "app" or module_name.startswith("app."):
        del sys.modules[module_name]

from app.modules.documents.application.services.document_service import DocumentService
from app.modules.documents.domain.entities.document import (
    Document,
    DocumentStatus,
    DocumentType,
)
from app.shared.domain.business_exceptions import (
    BusinessRuleViolationError,
    ValidationError,
)


class InMemoryDocumentRepo:
    def __init__(self) -> None:
        self.documents: dict[int, Document] = {}

    def save(self, document: Document) -> None:
        self.documents[document.document_id] = document

    def get(self, document_id: int) -> Document | None:
        return self.documents.get(document_id)

    def get_all(self) -> list[Document]:
        return list(self.documents.values())

    def update_status(self, document_id: int, new_status: DocumentStatus) -> None:
        self.documents[document_id].status = new_status

    def delete(self, document_id: int) -> None:
        del self.documents[document_id]


class RecordingPublisher:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    def publish(self, *, event_type: str, payload: dict[str, Any]) -> None:
        self.events.append((event_type, payload))


def _service() -> tuple[DocumentService, RecordingPublisher]:
    publisher = RecordingPublisher()
    return DocumentService(InMemoryDocumentRepo(), event_publisher=publisher), publisher


# ---------------------------------------------------------------------------
# Phase 0 – baseline: capture current behaviour before changing it
# ---------------------------------------------------------------------------


class TestDocumentCreationBaseline:
    def test_import_document_starts_as_draft(self) -> None:
        service, _ = _service()
        doc = service.create_import_document(
            to_warehouse_id=10,
            items=[{"product_id": 1, "quantity": 5, "unit_price": 10}],
            created_by="operator",
        )
        assert doc.status == DocumentStatus.DRAFT
        assert doc.doc_type == DocumentType.IMPORT

    def test_export_document_starts_as_draft(self) -> None:
        service, _ = _service()
        doc = service.create_export_document(
            from_warehouse_id=10,
            items=[{"product_id": 1, "quantity": 5, "unit_price": 10}],
            created_by="operator",
        )
        assert doc.status == DocumentStatus.DRAFT
        assert doc.doc_type == DocumentType.EXPORT

    def test_sale_document_starts_as_draft(self) -> None:
        service, _ = _service()
        doc = service.create_sale_document(
            from_warehouse_id=10,
            customer_id=1,
            items=[{"product_id": 1, "quantity": 5, "unit_price": 10}],
            created_by="operator",
        )
        assert doc.status == DocumentStatus.DRAFT
        assert doc.doc_type == DocumentType.SALE

    def test_transfer_document_starts_as_draft(self) -> None:
        service, _ = _service()
        doc = service.create_transfer_document(
            from_warehouse_id=10,
            to_warehouse_id=11,
            items=[{"product_id": 1, "quantity": 5, "unit_price": 0}],
            created_by="operator",
        )
        assert doc.status == DocumentStatus.DRAFT
        assert doc.doc_type == DocumentType.TRANSFER

    def test_creation_publishes_document_uploaded_event(self) -> None:
        service, publisher = _service()
        service.create_import_document(
            to_warehouse_id=10,
            items=[{"product_id": 1, "quantity": 5, "unit_price": 10}],
            created_by="operator",
        )
        assert any(et == "DocumentUploaded" for et, _ in publisher.events)

    def test_creation_with_empty_items_raises(self) -> None:
        service, _ = _service()
        with pytest.raises(ValidationError):
            service.create_import_document(
                to_warehouse_id=10,
                items=[],
                created_by="operator",
            )

    def test_transfer_same_warehouse_raises(self) -> None:
        service, _ = _service()
        with pytest.raises(BusinessRuleViolationError):
            service.create_transfer_document(
                from_warehouse_id=10,
                to_warehouse_id=10,
                items=[{"product_id": 1, "quantity": 1, "unit_price": 0}],
                created_by="operator",
            )


class TestDocumentPostingBaseline:
    def test_posting_sets_status_to_posted(self) -> None:
        service, _ = _service()
        doc = service.create_import_document(
            to_warehouse_id=10,
            items=[{"product_id": 1, "quantity": 5, "unit_price": 10}],
            created_by="operator",
        )
        posted = service.post_document(doc.document_id, approved_by="manager")
        assert posted.status == DocumentStatus.POSTED
        assert posted.approved_by == "manager"
        assert posted.posted_at is not None

    def test_posting_cancelled_document_raises(self) -> None:
        service, _ = _service()
        doc = service.create_import_document(
            to_warehouse_id=10,
            items=[{"product_id": 1, "quantity": 5, "unit_price": 10}],
            created_by="operator",
        )
        service.cancel_document(doc.document_id, cancelled_by="manager")
        with pytest.raises(BusinessRuleViolationError):
            service.post_document(doc.document_id, approved_by="manager")

    def test_posting_already_posted_document_is_idempotent(self) -> None:
        service, publisher = _service()
        doc = service.create_import_document(
            to_warehouse_id=10,
            items=[{"product_id": 1, "quantity": 5, "unit_price": 10}],
            created_by="operator",
        )
        service.post_document(doc.document_id, approved_by="manager")
        publisher.events.clear()
        result = service.post_document(doc.document_id, approved_by="manager")
        assert result.status == DocumentStatus.POSTED

    def test_posting_publishes_document_posted_and_movement_requested(self) -> None:
        service, publisher = _service()
        doc = service.create_import_document(
            to_warehouse_id=10,
            items=[{"product_id": 1, "quantity": 5, "unit_price": 10}],
            created_by="operator",
        )
        publisher.events.clear()
        service.post_document(doc.document_id, approved_by="manager")
        event_types = [et for et, _ in publisher.events]
        assert "DocumentPosted" in event_types
        assert "InventoryMovementRequested" in event_types


class TestDocumentPostingMovementPayloads:
    def test_posting_legacy_document_types_requests_inventory_movement(self) -> None:
        service, publisher = _service()
        created = [
            service.create_import_document(
                to_warehouse_id=10,
                items=[{"product_id": 100, "quantity": 2, "unit_price": 5}],
                created_by="operator",
            ),
            service.create_export_document(
                from_warehouse_id=10,
                items=[{"product_id": 101, "quantity": 3, "unit_price": 7}],
                created_by="operator",
            ),
            service.create_sale_document(
                from_warehouse_id=10,
                customer_id=20,
                items=[{"product_id": 102, "quantity": 4, "unit_price": 9}],
                created_by="operator",
            ),
            service.create_transfer_document(
                from_warehouse_id=10,
                to_warehouse_id=11,
                items=[{"product_id": 103, "quantity": 5, "unit_price": 0}],
                created_by="operator",
            ),
        ]
        publisher.events.clear()

        for document in created:
            service.post_document(document.document_id, approved_by="manager")

        movement_events = [
            payload
            for event_type, payload in publisher.events
            if event_type == "InventoryMovementRequested"
        ]
        assert [payload["doc_type"] for payload in movement_events] == [
            "IMPORT",
            "EXPORT",
            "SALE",
            "TRANSFER",
        ]
        assert all("status" not in payload for payload in movement_events) is True

    def test_import_movement_payload_has_destination_warehouse(self) -> None:
        service, publisher = _service()
        doc = service.create_import_document(
            to_warehouse_id=10,
            items=[{"product_id": 1, "quantity": 5, "unit_price": 10}],
            created_by="operator",
        )
        publisher.events.clear()
        service.post_document(doc.document_id, approved_by="manager")
        movement = next(
            p for et, p in publisher.events if et == "InventoryMovementRequested"
        )
        assert movement["to_warehouse_id"] == 10
        assert movement["items"][0]["product_id"] == 1
        assert movement["items"][0]["quantity"] == 5

    def test_export_movement_payload_has_source_warehouse(self) -> None:
        service, publisher = _service()
        doc = service.create_export_document(
            from_warehouse_id=10,
            items=[{"product_id": 1, "quantity": 3, "unit_price": 7}],
            created_by="operator",
        )
        publisher.events.clear()
        service.post_document(doc.document_id, approved_by="manager")
        movement = next(
            p for et, p in publisher.events if et == "InventoryMovementRequested"
        )
        assert movement["from_warehouse_id"] == 10

    def test_transfer_movement_payload_has_both_warehouses(self) -> None:
        service, publisher = _service()
        doc = service.create_transfer_document(
            from_warehouse_id=10,
            to_warehouse_id=11,
            items=[{"product_id": 1, "quantity": 2, "unit_price": 0}],
            created_by="operator",
        )
        publisher.events.clear()
        service.post_document(doc.document_id, approved_by="manager")
        movement = next(
            p for et, p in publisher.events if et == "InventoryMovementRequested"
        )
        assert movement["from_warehouse_id"] == 10
        assert movement["to_warehouse_id"] == 11


class TestDocumentCancellationBaseline:
    def test_cancelling_draft_document_sets_cancelled_status(self) -> None:
        service, _ = _service()
        doc = service.create_import_document(
            to_warehouse_id=10,
            items=[{"product_id": 1, "quantity": 5, "unit_price": 10}],
            created_by="operator",
        )
        cancelled = service.cancel_document(doc.document_id, cancelled_by="manager", reason="test")
        assert cancelled.status == DocumentStatus.CANCELLED

    def test_cancelling_posted_document_raises(self) -> None:
        service, _ = _service()
        doc = service.create_import_document(
            to_warehouse_id=10,
            items=[{"product_id": 1, "quantity": 5, "unit_price": 10}],
            created_by="operator",
        )
        service.post_document(doc.document_id, approved_by="manager")
        with pytest.raises(BusinessRuleViolationError):
            service.cancel_document(doc.document_id, cancelled_by="manager")

    def test_cancelling_already_cancelled_raises(self) -> None:
        service, _ = _service()
        doc = service.create_import_document(
            to_warehouse_id=10,
            items=[{"product_id": 1, "quantity": 5, "unit_price": 10}],
            created_by="operator",
        )
        service.cancel_document(doc.document_id, cancelled_by="manager")
        with pytest.raises(BusinessRuleViolationError):
            service.cancel_document(doc.document_id, cancelled_by="manager")


# ---------------------------------------------------------------------------
# Phase 0 – target-gap tests: expected failures documenting missing behaviour
# ---------------------------------------------------------------------------


@pytest.mark.xfail(reason="Phase 0 gap: approval/post still requests stock movement directly.")
def test_target_gap_approval_should_not_request_physical_stock_movement() -> None:
    service, publisher = _service()
    document = service.create_sale_document(
        from_warehouse_id=10,
        customer_id=20,
        items=[{"product_id": 100, "quantity": 2, "unit_price": 5}],
        created_by="operator",
    )
    publisher.events.clear()

    service.post_document(document.document_id, approved_by="manager")

    assert "InventoryMovementRequested" not in [
        event_type for event_type, _ in publisher.events
    ]


@pytest.mark.xfail(reason="Phase 0 gap: no execution confirmation with actual qty on documents.")
def test_target_gap_confirm_execution_should_accept_actual_quantity() -> None:
    service, _ = _service()
    doc = service.create_sale_document(
        from_warehouse_id=10,
        customer_id=1,
        items=[{"product_id": 1, "quantity": 10, "unit_price": 5}],
        created_by="operator",
    )
    service.post_document(doc.document_id, approved_by="manager")
    service.confirm_execution(
        document_id=doc.document_id,
        lines=[{"product_id": 1, "executed_qty": 8}],
        executed_by="warehouse_worker",
    )


@pytest.mark.xfail(reason="Phase 0 gap: document only has DRAFT/POSTED/CANCELLED statuses.")
def test_target_gap_document_should_support_requested_status() -> None:
    assert hasattr(DocumentStatus, "REQUESTED")


@pytest.mark.xfail(reason="Phase 0 gap: document only has DRAFT/POSTED/CANCELLED statuses.")
def test_target_gap_document_should_support_in_progress_status() -> None:
    assert hasattr(DocumentStatus, "IN_PROGRESS")


@pytest.mark.xfail(reason="Phase 0 gap: document only has DRAFT/POSTED/CANCELLED statuses.")
def test_target_gap_document_should_support_completed_status() -> None:
    assert hasattr(DocumentStatus, "COMPLETED")
