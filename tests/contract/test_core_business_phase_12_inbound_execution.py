from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# Import domain and service objects
# ---------------------------------------------------------------------------
DOCUMENTS_SRC = ROOT_DIR / "Services/documents-service/src"
sys.path.insert(0, str(DOCUMENTS_SRC))
for module_name in list(sys.modules):
    if module_name == "app" or module_name.startswith("app."):
        del sys.modules[module_name]

from app.modules.documents.domain.entities.document import (
    Document,
    DocumentProduct,
    DocumentStatus,
    DocumentType,
)
from app.modules.documents.application.services.document_service import DocumentService
from app.shared.domain.business_exceptions import (
    InvalidDocumentStatusError,
    ValidationError,
)

INVENTORY_SRC = ROOT_DIR / "Services/inventory-service/src"
for module_name in list(sys.modules):
    if module_name == "app" or module_name.startswith("app."):
        del sys.modules[module_name]
sys.path.insert(0, str(INVENTORY_SRC))

from app.modules.inventory.application.services.inventory_service import InventoryService


# ---------------------------------------------------------------------------
# InMemory / Mock components for testing service logic
# ---------------------------------------------------------------------------
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
        if document_id in self.documents:
            self.documents[document_id].status = new_status


class RecordingPublisher:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    def publish(self, *, event_type: str, payload: dict[str, Any]) -> None:
        self.events.append((event_type, payload))


# ===========================================================================
# Phase 12 – Inbound Execution Verification
# ===========================================================================
class TestProtoDefinitionsPhase12:
    def test_proto_has_transaction_type_and_reason_code(self) -> None:
        proto_file = ROOT_DIR / "proto/wms/documents/v1/documents.proto"
        content = proto_file.read_text()
        assert "string transaction_type = " in content
        assert "string reason_code = " in content


class TestDocumentServiceLogicPhase12:
    def test_create_import_document_stores_transaction_type_and_reason_code(self) -> None:
        repo = InMemoryDocumentRepo()
        publisher = RecordingPublisher()
        service = DocumentService(repo, event_publisher=publisher)

        # Create IMPORT document with sub-type PURCHASE_RECEIPT
        doc = service.create_import_document(
            to_warehouse_id=2,
            items=[{"product_id": 202, "quantity": 10, "unit_price": 5.0}],
            created_by="tester",
            transaction_type="PURCHASE_RECEIPT",
            reason_code="EXPIRY_REPLACEMENT"
        )
        assert doc.transaction_type == "PURCHASE_RECEIPT"
        assert doc.reason_code == "EXPIRY_REPLACEMENT"

        saved_doc = repo.get(doc.document_id)
        assert saved_doc is not None
        assert saved_doc.transaction_type == "PURCHASE_RECEIPT"
        assert saved_doc.reason_code == "EXPIRY_REPLACEMENT"

    def test_adjustment_in_requires_reason_code(self) -> None:
        repo = InMemoryDocumentRepo()
        publisher = RecordingPublisher()
        service = DocumentService(repo, event_publisher=publisher)

        # Create ADJUSTMENT_IN without reason code
        doc = service.create_import_document(
            to_warehouse_id=2,
            items=[{"product_id": 202, "quantity": 10, "unit_price": 0.0}],
            created_by="tester",
            transaction_type="ADJUSTMENT_IN",
            reason_code=None
        )
        assert doc.transaction_type == "ADJUSTMENT_IN"
        assert doc.reason_code is None

        # Verify validation error is raised during confirm_execution
        service.start_execution(doc.document_id)
        with pytest.raises(ValidationError, match="Reason code is required for ADJUSTMENT_IN"):
            service.confirm_execution(doc.document_id, [{"product_id": 202, "quantity": 10}])

        # Setting reason code should allow confirming
        doc.reason_code = "DAMAGE"
        repo.save(doc)
        service.confirm_execution(doc.document_id, [{"product_id": 202, "quantity": 10}])
        assert repo.get(doc.document_id).status == DocumentStatus.EXECUTED


class TestApiGatewayRoutesPhase12:
    def test_routes_pass_new_fields(self) -> None:
        routes_file = ROOT_DIR / "Services/api-gateway/src/api_gateway/routes.py"
        content = routes_file.read_text()
        assert "transaction_type=payload.transaction_type or" in content
        assert "reason_code=payload.reason_code or" in content
        assert 'target_tx_type == "ADJUSTMENT_IN" and not doc.reason_code' in content
        assert "ConfirmInventoryTransactionRequest" in content
