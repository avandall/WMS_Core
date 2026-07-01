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
# Phase 13 – Outbound Non-Sales Execution Verification
# ===========================================================================
class TestDocumentServiceLogicPhase13:
    def test_outbound_non_sales_reason_code_validations(self) -> None:
        repo = InMemoryDocumentRepo()
        publisher = RecordingPublisher()
        service = DocumentService(repo, event_publisher=publisher)

        # ADJUSTMENT_OUT
        doc1 = service.create_export_document(
            from_warehouse_id=1,
            items=[{"product_id": 202, "quantity": 10, "unit_price": 5.0}],
            created_by="tester",
            transaction_type="ADJUSTMENT_OUT",
            reason_code=None
        )
        service.start_execution(doc1.document_id)
        with pytest.raises(ValidationError, match="Reason code is required for ADJUSTMENT_OUT"):
            service.confirm_execution(doc1.document_id, [{"product_id": 202, "quantity": 10}])

        # SCRAP
        doc2 = service.create_export_document(
            from_warehouse_id=1,
            items=[{"product_id": 202, "quantity": 10, "unit_price": 5.0}],
            created_by="tester",
            transaction_type="SCRAP",
            reason_code=None
        )
        service.start_execution(doc2.document_id)
        with pytest.raises(ValidationError, match="Reason code is required for SCRAP"):
            service.confirm_execution(doc2.document_id, [{"product_id": 202, "quantity": 10}])

        # INTERNAL_CONSUMPTION
        doc3 = service.create_export_document(
            from_warehouse_id=1,
            items=[{"product_id": 202, "quantity": 10, "unit_price": 5.0}],
            created_by="tester",
            transaction_type="INTERNAL_CONSUMPTION",
            reason_code=None
        )
        service.start_execution(doc3.document_id)
        with pytest.raises(ValidationError, match="Reason code is required for INTERNAL_CONSUMPTION"):
            service.confirm_execution(doc3.document_id, [{"product_id": 202, "quantity": 10}])

        # PURCHASE_RETURN_SHIPMENT (does not require reason code)
        doc4 = service.create_export_document(
            from_warehouse_id=1,
            items=[{"product_id": 202, "quantity": 10, "unit_price": 5.0}],
            created_by="tester",
            transaction_type="PURCHASE_RETURN_SHIPMENT",
            reason_code=None
        )
        service.start_execution(doc4.document_id)
        service.confirm_execution(doc4.document_id, [{"product_id": 202, "quantity": 10}])
        assert repo.get(doc4.document_id).status == DocumentStatus.EXECUTED


class TestApiGatewayRoutesPhase13:
    def test_routes_generalize_stock_coordination(self) -> None:
        routes_file = ROOT_DIR / "Services/api-gateway/src/api_gateway/routes.py"
        content = routes_file.read_text()
        assert "target_tx_type in REQUIRES_RESERVATION" in content
        assert "target_tx_type in REQUIRES_REASON_CODE" in content
        assert "is_outbound = target_tx_type in OUTBOUND_TYPES" in content
