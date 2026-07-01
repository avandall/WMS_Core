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


class DummyInventoryRepo:
    def __init__(self) -> None:
        self.reservations: dict[int, Any] = {}
        self.warehouse_stock: dict[tuple[int, int], int] = {}
        self.transactions: list[dict] = []
        self.session = Mock()

    def consume_reservation(self, reservation_id: int, consumed_qty: int) -> None:
        # Mock behavior
        pass

    def list_transactions(self, **kwargs) -> list[dict]:
        return self.transactions

    def write_transaction(self, **kwargs) -> dict:
        self.transactions.append(kwargs)
        return {"id": len(self.transactions)}

    def record_movement_event(self, **kwargs) -> None:
        pass


# ===========================================================================
# Phase 10 & 11 – Contract & Logic Verification
# ===========================================================================
class TestProtoRPCDefinitions:
    def test_proto_has_phase_10_rpcs(self) -> None:
        proto_file = ROOT_DIR / "proto/wms/documents/v1/documents.proto"
        content = proto_file.read_text()
        assert "rpc StartExecution" in content
        assert "rpc ConfirmExecution" in content
        assert "rpc CompleteRequest" in content

    def test_inventory_proto_has_phase_10_rpc(self) -> None:
        proto_file = ROOT_DIR / "proto/wms/inventory/v1/inventory.proto"
        content = proto_file.read_text()
        assert "rpc ConfirmInventoryTransaction" in content


class TestDocumentServiceLogic:
    def test_document_service_has_lifecycle_methods(self) -> None:
        service_file = ROOT_DIR / "Services/documents-service/src/app/modules/documents/application/services/document_service.py"
        content = service_file.read_text()
        assert "def start_execution" in content
        assert "def confirm_execution" in content
        assert "def complete_request" in content

    def test_document_status_has_new_statuses(self) -> None:
        assert hasattr(DocumentStatus, "IN_PROGRESS")
        assert hasattr(DocumentStatus, "EXECUTED")
        assert hasattr(DocumentStatus, "COMPLETED")

    def test_workflow_transitions_correctly(self) -> None:
        repo = InMemoryDocumentRepo()
        publisher = RecordingPublisher()
        service = DocumentService(repo, event_publisher=publisher)

        # Create SALE document
        doc = Document(
            document_id=101,
            doc_type=DocumentType.SALE,
            from_warehouse_id=1,
            items=[DocumentProduct(product_id=202, quantity=10, unit_price=5.0)],
            created_by="tester"
        )
        repo.save(doc)

        # 1. Start Execution
        service.start_execution(101)
        updated = repo.get(101)
        assert updated.status == DocumentStatus.IN_PROGRESS
        assert updated.execution_started_at is not None

        # 2. Confirm Execution (e.g. with partial qty 8)
        service.confirm_execution(101, items=[{"product_id": 202, "quantity": 8}])
        updated = repo.get(101)
        assert updated.status == DocumentStatus.EXECUTED
        assert updated.items[0].executed_qty == 8
        assert updated.items[0].difference_qty == 2

        # 3. Complete Request
        service.complete_request(101)
        updated = repo.get(101)
        assert updated.status == DocumentStatus.COMPLETED
        assert updated.completed_at is not None


class TestInventoryServiceConfirmTransaction:
    def test_inventory_service_has_confirm_transaction_method(self) -> None:
        service_file = ROOT_DIR / "Services/inventory-service/src/app/modules/inventory/application/services/inventory_service.py"
        content = service_file.read_text()
        assert "def confirm_inventory_transaction" in content
        assert "def consume_reservation" in content


class TestApiGatewayRoutes:
    def test_routes_have_rest_endpoints(self) -> None:
        routes_file = ROOT_DIR / "Services/api-gateway/src/api_gateway/routes.py"
        content = routes_file.read_text()
        assert '"/documents/{document_id}/start-execution"' in content
        assert '"/documents/{document_id}/confirm"' in content
        assert '"/documents/{document_id}/complete"' in content
