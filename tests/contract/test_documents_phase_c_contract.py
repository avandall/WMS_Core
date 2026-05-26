from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[2]
DOCUMENTS_SRC = ROOT_DIR / "Services/documents-service/src"
sys.path.insert(0, str(DOCUMENTS_SRC))

from app.modules.documents.application.services.document_service import DocumentService
from app.modules.documents.domain.entities.document import Document, DocumentStatus
from app.modules.documents.domain.exceptions import InvalidDocumentStatusError


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
        document = self.documents[document_id]
        document.status = new_status

    def delete(self, document_id: int) -> None:
        del self.documents[document_id]


class RecordingPublisher:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    def publish(self, *, event_type: str, payload: dict[str, Any]) -> None:
        self.events.append((event_type, payload))


def _service() -> tuple[DocumentService, InMemoryDocumentRepo, RecordingPublisher]:
    repo = InMemoryDocumentRepo()
    publisher = RecordingPublisher()
    return DocumentService(repo, event_publisher=publisher), repo, publisher


def test_document_creation_emits_document_uploaded_with_external_id_snapshots() -> None:
    service, _, publisher = _service()

    document = service.create_sale_document(
        from_warehouse_id=10,
        customer_id=20,
        items=[{"product_id": 30, "quantity": 2, "unit_price": 5}],
        created_by="operator",
        request_id="req-1",
    )

    assert publisher.events == [
        (
            "DocumentUploaded",
            {
                "event_id": f"documents:{document.document_id}:uploaded",
                "request_id": "req-1",
                "entity_type": "document",
                "entity_id": document.document_id,
                "document_id": document.document_id,
                "doc_type": "SALE",
                "status": "DRAFT",
                "customer_id": 20,
                "from_warehouse_id": 10,
                "to_warehouse_id": None,
                "items": [{"product_id": 30, "quantity": 2, "unit_price": 5.0}],
            },
        )
    ]


def test_post_document_is_idempotent_and_requests_inventory_movement() -> None:
    service, _, publisher = _service()
    document = service.create_import_document(
        to_warehouse_id=10,
        items=[{"product_id": 30, "quantity": 2, "unit_price": 5}],
        created_by="operator",
    )
    publisher.events.clear()

    first = service.post_document(document.document_id, "manager", request_id="req-post")
    second = service.post_document(document.document_id, "manager", request_id="req-post")

    assert first is second
    assert second.status == DocumentStatus.POSTED
    assert [event_type for event_type, _ in publisher.events] == [
        "DocumentPosted",
        "InventoryMovementRequested",
        "DocumentPosted",
        "InventoryMovementRequested",
    ]
    assert publisher.events[0][1]["event_id"] == f"documents:{document.document_id}:posted"
    assert publisher.events[2][1]["event_id"] == f"documents:{document.document_id}:posted"
    assert publisher.events[1][1]["event_id"] == (
        f"documents:{document.document_id}:inventory-movement-requested"
    )
    assert publisher.events[3][1]["event_id"] == (
        f"documents:{document.document_id}:inventory-movement-requested"
    )


def test_cancelled_document_cannot_be_posted() -> None:
    service, _, _ = _service()
    document = service.create_export_document(
        from_warehouse_id=10,
        items=[{"product_id": 30, "quantity": 2, "unit_price": 5}],
        created_by="operator",
    )

    service.cancel_document(document.document_id, cancelled_by="manager", reason="mistake")

    try:
        service.post_document(document.document_id, "manager")
    except InvalidDocumentStatusError as exc:
        assert "Cannot post cancelled document" in str(exc)
    else:
        raise AssertionError("cancelled document was posted")
