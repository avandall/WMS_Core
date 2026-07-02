from __future__ import annotations

import os
# Ensure a valid database URL is configured before any settings are loaded
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock
from typing import Any, Optional

ROOT_DIR = Path(__file__).resolve().parents[2]

# Helper to load a service's sys.path correctly
def _load_service(src_path: Path):
    sys.path.insert(0, str(src_path))
    for module_name in list(sys.modules):
        if module_name == "app" or module_name.startswith("app."):
            del sys.modules[module_name]

# ==========================================
# 1. Documents Service Event Enrichment Tests
# ==========================================

class DummyDocumentRepo:
    def __init__(self):
        self.committed = False
        self.db = {}

    def get(self, document_id: int):
        return self.db.get(document_id)

    def save(self, doc):
        self.db[doc.document_id] = doc

    def commit(self):
        self.committed = True


def test_document_service_publishes_document_approved() -> None:
    _load_service(ROOT_DIR / "Services/documents-service/src")
    from app.modules.documents.application.services.document_service import DocumentService
    from app.modules.documents.domain.entities.document import DocumentType, DocumentStatus

    repo = DummyDocumentRepo()
    publisher = Mock()
    service = DocumentService(repo, event_publisher=publisher)  # type: ignore[arg-type]

    # Create dummy document with DRAFT status using real Enums
    doc = Mock()
    doc.document_id = 42
    doc.doc_type = DocumentType.SALE
    doc.status = DocumentStatus.DRAFT
    doc.customer_id = 9
    doc.from_warehouse_id = 1
    doc.to_warehouse_id = None
    doc.items = [Mock(product_id=101, quantity=5, unit_price=10.0)]
    doc.posted_event_payload = Mock(return_value={})
    doc._item_snapshots = Mock(return_value=[])
    repo.save(doc)

    res = service.approve_request(42, "user_admin")

    # Verify both legacy DocumentPosted and new DocumentApproved are published
    published_types = [call.kwargs.get("event_type") or call.args[0] for call in publisher.publish.call_args_list]
    assert "DocumentApproved" in published_types
    assert "DocumentPosted" in published_types

    approved_call = [call for call in publisher.publish.call_args_list if (call.kwargs.get("event_type") or call.args[0]) == "DocumentApproved"][0]
    payload = approved_call.kwargs.get("payload") or approved_call.args[1]
    assert payload["document_id"] == 42
    assert payload["entity_type"] == "document"


def test_document_execution_started_completed_enrichment() -> None:
    _load_service(ROOT_DIR / "Services/documents-service/src")
    from app.modules.documents.application.services.document_service import DocumentService
    from app.modules.documents.domain.entities.document import DocumentType, DocumentStatus

    repo = DummyDocumentRepo()
    publisher = Mock()
    service = DocumentService(repo, event_publisher=publisher)  # type: ignore[arg-type]

    doc = Mock()
    doc.document_id = 43
    doc.doc_type = DocumentType.SALE
    doc.status = DocumentStatus.APPROVED
    doc.customer_id = 9
    doc.from_warehouse_id = 2
    doc.to_warehouse_id = None
    doc.items = [Mock(product_id=102, quantity=10, unit_price=5.0)]
    doc._item_snapshots = Mock(return_value=[])
    repo.save(doc)

    # Trigger warehouse execution start
    service.start_execution(43, "evt_req_started")
    
    # Update status for mock so completion can proceed
    doc.status = DocumentStatus.EXECUTED
    doc._items = {}
    
    # Trigger completion
    service.complete_request(43, "evt_req_completed")

    published_calls = {
        (call.kwargs.get("event_type") or call.args[0]): (call.kwargs.get("payload") or call.args[1])
        for call in publisher.publish.call_args_list
    }

    assert "WarehouseExecutionStarted" in published_calls
    assert "DocumentCompleted" in published_calls

    started = published_calls["WarehouseExecutionStarted"]
    assert started["document_id"] == 43
    assert started["warehouse_id"] == 2
    assert started["entity_type"] == "document"

    completed = published_calls["DocumentCompleted"]
    assert completed["document_id"] == 43
    assert completed["warehouse_id"] == 2
    assert completed["entity_type"] == "document"


# ==========================================
# 2. Inventory Service Ledger Event Tests
# ==========================================

class DummySession:
    def __init__(self):
        self.committed = False
        self.db = {}

    def get(self, model, identifier):
        return self.db.get((model, identifier))

    def add(self, instance):
        pass

    def commit(self):
        self.committed = True


class DummyInventoryRepoWithSession:
    def __init__(self):
        self.session = DummySession()
        self.transactions = []
        self.stock = {}

    def get_quantity(self, product_id: int) -> int:
        return 100

    def has_movement_event(self, event_id: str) -> bool:
        return False

    def record_movement_event(self, event_id: str, movement_type: str, document_id: Optional[int], payload: dict[str, Any]) -> None:
        pass

    def adjust_warehouse_quantity(self, product_id: int, warehouse_id: int, quantity_delta: int) -> None:
        key = (product_id, warehouse_id)
        if key not in self.stock:
            self.stock[key] = {"physical": 0, "in_transit": 0}
        self.stock[key]["physical"] += quantity_delta

    def adjust_warehouse_in_transit(self, product_id: int, warehouse_id: int, quantity_delta: int) -> None:
        key = (product_id, warehouse_id)
        if key not in self.stock:
            self.stock[key] = {"physical": 0, "in_transit": 0}
        self.stock[key]["in_transit"] += quantity_delta

    def adjust_quantity(self, product_id: int, quantity_delta: int) -> None:
        pass

    def write_transaction(self, **kwargs) -> dict:
        tx = {
            "id": len(self.transactions) + 1,
            "transaction_type": kwargs.get("transaction_type") or "UNKNOWN",
            "product_id": kwargs.get("product_id") or 0,
            "warehouse_id": kwargs.get("warehouse_id") or 0,
            "quantity": kwargs.get("quantity") or 0,
            "document_id": kwargs.get("document_id"),
            "document_line_id": kwargs.get("document_line_id"),
            "created_at": "2026-07-01T12:00:00",
            "idempotency_key": kwargs.get("idempotency_key"),
        }
        self.transactions.append(tx)
        return tx

    def list_transactions(self, *, product_id: int, warehouse_id: int, limit: int = 1, transaction_type: Optional[str] = None) -> list[dict]:
        txs = [
            tx for tx in self.transactions
            if tx["product_id"] == product_id and tx["warehouse_id"] == warehouse_id
        ]
        if transaction_type:
            txs = [tx for tx in txs if tx["transaction_type"] == transaction_type]
        return txs[-limit:]

    def reserve_stock(self, product_id, warehouse_id, qty, doc_id) -> int:
        return 99

    def release_reservation(self, res_id, qty) -> None:
        pass


def test_inventory_service_writes_publish_transaction_recorded() -> None:
    _load_service(ROOT_DIR / "Services/inventory-service/src")
    from app.modules.inventory.application.services.inventory_service import InventoryService

    repo = DummyInventoryRepoWithSession()
    publisher = Mock()
    service = InventoryService(repo, publisher)  # type: ignore[arg-type]

    # Perform simple adjustment
    service.adjust_inventory(product_id=201, quantity_delta=10, warehouse_id=5, event_id="evt_adj_1")

    # Verify InventoryTransactionRecorded was published
    published_calls = [
        (call.kwargs.get("event_type") or call.args[0], call.kwargs.get("payload") or call.args[1])
        for call in publisher.publish.call_args_list
    ]
    assert len(published_calls) > 0
    evt_type, payload = published_calls[0]
    assert evt_type == "InventoryTransactionRecorded"
    assert payload["product_id"] == 201
    assert payload["warehouse_id"] == 5
    assert payload["quantity"] == 10
    assert payload["transaction_type"] == "ADJUSTMENT_IN"


def test_inventory_release_reservation_enriches_details() -> None:
    _load_service(ROOT_DIR / "Services/inventory-service/src")
    from app.modules.inventory.application.services.inventory_service import InventoryService
    from app.modules.inventory.infrastructure.models.stock_reservation import StockReservationModel

    repo = DummyInventoryRepoWithSession()
    publisher = Mock()
    service = InventoryService(repo, publisher)  # type: ignore[arg-type]

    # Seed mock reservation in mock session database
    mock_res = Mock(spec=StockReservationModel)
    mock_res.product_id = 301
    mock_res.warehouse_id = 2
    mock_res.document_id = 88
    mock_res.reserved_qty = 15
    repo.session.db[(StockReservationModel, 99)] = mock_res

    # Release the reservation
    service.release_reservation(reservation_id=99, released_qty=10, event_id="evt_release_1")

    # Find ReservationReleased event in publisher calls
    released_call = [
        call for call in publisher.publish.call_args_list
        if (call.kwargs.get("event_type") or call.args[0]) == "ReservationReleased"
    ][0]
    payload = released_call.kwargs.get("payload") or released_call.args[1]

    # Verify enrichment fields from retrieved reservation model
    assert payload["reservation_id"] == 99
    assert payload["released_qty"] == 10
    assert payload["product_id"] == 301
    assert payload["warehouse_id"] == 2
    assert payload["document_id"] == 88


def test_inventory_confirm_transaction_publishes_transfer_events() -> None:
    _load_service(ROOT_DIR / "Services/inventory-service/src")
    from app.modules.inventory.application.services.inventory_service import InventoryService

    repo = DummyInventoryRepoWithSession()
    publisher = Mock()
    service = InventoryService(repo, publisher)  # type: ignore[arg-type]

    # Confirm a transfer issue
    service.confirm_inventory_transaction(
        transaction_type="TRANSFER_ISSUE",
        product_id=401,
        warehouse_id=1,
        quantity=20,
        idempotency_key="confirm_111222_401_1_issue",
        user_id="user_picker",
    )

    # Confirm a transfer receipt
    service.confirm_inventory_transaction(
        transaction_type="TRANSFER_RECEIPT",
        product_id=401,
        warehouse_id=2,
        quantity=20,
        idempotency_key="confirm_111222_401_2_receipt",
        source_warehouse_id=1,
        user_id="user_receiver",
    )

    published_events = {
        (call.kwargs.get("event_type") or call.args[0]): (call.kwargs.get("payload") or call.args[1])
        for call in publisher.publish.call_args_list
    }

    assert "TransferIssued" in published_events
    assert "TransferReceived" in published_events

    issued = published_events["TransferIssued"]
    assert issued["document_id"] == 111222
    assert issued["product_id"] == 401
    assert issued["warehouse_id"] == 1
    assert issued["quantity"] == 20
    assert issued["user_id"] == "user_picker"

    received = published_events["TransferReceived"]
    assert received["document_id"] == 111222
    assert received["product_id"] == 401
    assert received["warehouse_id"] == 2
    assert received["source_warehouse_id"] == 1
    assert received["quantity"] == 20
    assert received["user_id"] == "user_receiver"


# ==========================================
# 3. Reporting Projections Tests
# ==========================================

class FakeQuery:
    def __init__(self, rows: list[object]) -> None:
        self.rows = rows
        self.criteria = ()

    def filter(self, *args, **kwargs):
        _ = args, kwargs
        self.criteria = args
        return self

    def order_by(self, *args, **kwargs):
        _ = args, kwargs
        return self

    def all(self) -> list[object]:
        return self.rows

    def one_or_none(self):
        for criterion in self.criteria:
            left = getattr(criterion, "left", None)
            right = getattr(criterion, "right", None)
            field = getattr(left, "key", None)
            value = getattr(right, "value", None)
            if field and value is not None:
                for row in self.rows:
                    if getattr(row, field, None) == value:
                        return row
                return None
        return self.rows[0] if self.rows else None


class FakeSessionForReporting:
    def __init__(self) -> None:
        self.objects: dict[tuple[type, object], object] = {}

    def add(self, obj: object) -> None:
        key = self._key(obj)
        self.objects[key] = obj

    def get(self, model: type, identity: object):
        return self.objects.get((model, identity))

    def query(self, model: type) -> FakeQuery:
        rows = [obj for (obj_model, _), obj in self.objects.items() if obj_model is model]
        return FakeQuery(rows)

    @staticmethod
    def _key(obj: object) -> tuple[type, object]:
        for attr in ("event_id", "product_id", "document_id", "warehouse_id"):
            if hasattr(obj, attr):
                val = getattr(obj, attr)
                if val is not None:
                    return (type(obj), val)
        raise AssertionError(f"Unsupported fake model: {obj!r}")


class EnvelopeStub:
    def __init__(self, event_type: str, payload: dict):
        self.type = event_type
        self.payload = payload
        self.event_id = payload.get("event_id") or "stub-id"
        self.source = payload.get("source") or "stub-source"
        self.occurred_at = payload.get("occurred_at") or "2026-07-01T12:00:00"


def test_reporting_projects_executed_quantity_and_warehouse_matrix() -> None:
    _load_service(ROOT_DIR / "Services/reporting-service/src")
    from app.modules.reporting.infrastructure.repositories.read_model_repo import ReportingReadModelRepo
    from app.modules.reporting.infrastructure.models.projections import DocumentSummary, InventorySummary

    session = FakeSessionForReporting()
    repo = ReportingReadModelRepo(session)  # type: ignore[arg-type]

    # 1. Project DocumentUploaded to create DocumentSummary
    repo.record_event(
        stream_id="doc-1",
        envelope=EnvelopeStub(
            "DocumentUploaded",
            {
                "event_id": "doc-uploaded-1",
                "document_id": 501,
                "doc_type": "SALE",
                "status": "DRAFT",
                "customer_id": 5,
                "from_warehouse_id": 1,
                "items": [{"product_id": 801, "quantity": 100, "unit_price": 4.5}],
            },
        ),  # type: ignore[arg-type]
    )

    # 2. Project WarehouseExecutionConfirmed to verify executed_quantity update
    repo.record_event(
        stream_id="exec-1",
        envelope=EnvelopeStub(
            "WarehouseExecutionConfirmed",
            {
                "event_id": "exec-conf-1",
                "document_id": 501,
                "items": [{"product_id": 801, "quantity": 95}],
            },
        ),  # type: ignore[arg-type]
    )

    doc_summary = session.get(DocumentSummary, 501)
    assert doc_summary is not None
    assert doc_summary.status == "EXECUTED"
    assert doc_summary.executed_quantity == 95

    # 3. Project InventoryTransactionRecorded (RESERVATION) to verify reserved_qty matrix increment
    repo.record_event(
        stream_id="tx-1",
        envelope=EnvelopeStub(
            "InventoryTransactionRecorded",
            {
                "event_id": "tx-rec-1",
                "transaction_type": "RESERVATION",
                "product_id": 801,
                "warehouse_id": 1,
                "quantity": 10,
                "document_id": 501,
            },
        ),  # type: ignore[arg-type]
    )

    inv_summary = session.get(InventorySummary, 801)
    assert inv_summary is not None
    assert inv_summary.warehouse_matrix["1"]["reserved_qty"] == 10
    assert inv_summary.warehouse_matrix["1"]["available_qty"] == -10  # 0 physical - 10 reserved

    # 4. Project InventoryTransactionRecorded (RESERVATION_CONSUME) to verify consumption adjustment
    repo.record_event(
        stream_id="tx-2",
        envelope=EnvelopeStub(
            "InventoryTransactionRecorded",
            {
                "event_id": "tx-rec-2",
                "transaction_type": "RESERVATION_CONSUME",
                "product_id": 801,
                "warehouse_id": 1,
                "quantity": 10,
                "document_id": 501,
            },
        ),  # type: ignore[arg-type]
    )

    inv_summary = session.get(InventorySummary, 801)
    assert inv_summary is not None
    # reservation consume reduces physical stock by 10 and reserved by 10
    assert inv_summary.warehouse_matrix["1"]["physical_qty"] == -10
    assert inv_summary.warehouse_matrix["1"]["reserved_qty"] == 0
    assert inv_summary.warehouse_matrix["1"]["available_qty"] == -10


# ==========================================
# 4. AI Query Template Extractor Tests
# ==========================================

def test_ai_extractor_heuristic_parses_new_wms_terms() -> None:
    # Clear sys path to avoid pollution, but ai-service uses standard libs mostly
    sys.path.insert(0, str(ROOT_DIR / "Services/ai-service/src"))
    from ai_service.pipeline.templates import HeuristicQueryTemplateExtractor

    extractor = HeuristicQueryTemplateExtractor()

    # Query for available quantity
    template_av = extractor.extract(question="available stock of product 202 in warehouse 5")
    assert template_av.intent == "inventory_lookup"
    assert "available_qty" in template_av.metrics
    assert template_av.filters["product_id"] == "202"
    assert template_av.filters["warehouse_id"] == "5"

    # Query for reserved stock
    template_res = extractor.extract(question="reserved stock of product 101")
    assert template_res.intent == "inventory_lookup"
    assert "reserved_qty" in template_res.metrics
    assert template_res.filters["product_id"] == "101"

    # Query for in-transit stock
    template_transit = extractor.extract(question="what is in-transit inventory of product 102")
    assert template_transit.intent == "inventory_lookup"
    assert "in_transit_qty" in template_transit.metrics
    assert template_transit.filters["product_id"] == "102"

    # Query for transaction type or ledger
    template_ledger = extractor.extract(question="show stock ledger for warehouse 2")
    assert template_ledger.intent == "document_lookup"
    assert "transaction_type" in template_ledger.metrics
    assert template_ledger.filters["warehouse_id"] == "2"

    # Query for pending execution
    template_pending = extractor.extract(question="list pending execution documents")
    assert template_pending.intent == "document_lookup"
    assert "status" in template_pending.metrics
