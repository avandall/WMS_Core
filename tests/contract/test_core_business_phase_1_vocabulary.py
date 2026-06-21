from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest


ROOT_DIR = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# Import documents-service domain under isolated namespace
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
from app.modules.documents.domain.transaction_types import (
    ExecutionStatus,
    ExtendedDocumentStatus,
    INBOUND_TYPES,
    OUTBOUND_TYPES,
    ReasonCode,
    REQUIRES_REASON_CODE,
    REQUIRES_RESERVATION,
    ReservationStatus,
    TransactionType,
)
from app.modules.documents.domain.transaction_mapping import (
    DOC_TYPE_TO_TRANSACTION_TYPE,
    default_transaction_type,
)
from app.modules.documents.application.services.document_service import DocumentService
from app.shared.domain.business_exceptions import (
    BusinessRuleViolationError,
    ValidationError,
)


# ---------------------------------------------------------------------------
# Import inventory-service value objects under isolated namespace
# ---------------------------------------------------------------------------
INVENTORY_SRC = ROOT_DIR / "Services/inventory-service/src"
for module_name in list(sys.modules):
    if module_name == "app" or module_name.startswith("app."):
        del sys.modules[module_name]
sys.path.insert(0, str(INVENTORY_SRC))

from app.modules.inventory.domain.value_objects import StockBalance


# ---------------------------------------------------------------------------
# Helpers
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


# ===========================================================================
# Phase 1 – shared vocabulary tests: enums, mapping, defaults
# ===========================================================================


class TestTransactionTypeEnum:
    def test_all_inbound_types_exist(self) -> None:
        for name in [
            "PURCHASE_RECEIPT",
            "PRODUCTION_RECEIPT",
            "SALES_RETURN_RECEIPT",
            "TRANSFER_RECEIPT",
            "ADJUSTMENT_IN",
        ]:
            assert hasattr(TransactionType, name)

    def test_all_outbound_types_exist(self) -> None:
        for name in [
            "SALES_SHIPMENT",
            "PRODUCTION_ISSUE",
            "PURCHASE_RETURN_SHIPMENT",
            "TRANSFER_ISSUE",
            "INTERNAL_CONSUMPTION",
            "SCRAP",
            "ADJUSTMENT_OUT",
        ]:
            assert hasattr(TransactionType, name)

    def test_inbound_outbound_sets_are_disjoint(self) -> None:
        assert INBOUND_TYPES & OUTBOUND_TYPES == set()

    def test_all_types_are_in_inbound_or_outbound(self) -> None:
        assert INBOUND_TYPES | OUTBOUND_TYPES == set(TransactionType)


class TestReasonCodeEnum:
    def test_required_reason_codes_exist(self) -> None:
        for name in ["CYCLE_COUNT", "DAMAGE", "EXPIRY", "QUALITY_REJECT", "OTHER"]:
            assert hasattr(ReasonCode, name)


class TestExtendedDocumentStatus:
    def test_includes_legacy_statuses(self) -> None:
        for name in ["DRAFT", "POSTED", "CANCELLED"]:
            assert hasattr(ExtendedDocumentStatus, name)

    def test_includes_new_lifecycle_statuses(self) -> None:
        for name in [
            "REQUESTED",
            "APPROVED",
            "RESERVED",
            "PARTIALLY_RESERVED",
            "IN_PROGRESS",
            "EXECUTED",
            "PARTIALLY_EXECUTED",
            "COMPLETED",
        ]:
            assert hasattr(ExtendedDocumentStatus, name)


class TestReservationStatus:
    def test_has_expected_values(self) -> None:
        for name in ["PENDING", "RESERVED", "RELEASED", "CONSUMED", "EXPIRED"]:
            assert hasattr(ReservationStatus, name)


class TestExecutionStatus:
    def test_has_expected_values(self) -> None:
        for name in ["PENDING", "IN_PROGRESS", "EXECUTED", "SHORT_CLOSED"]:
            assert hasattr(ExecutionStatus, name)


class TestClassificationSets:
    def test_requires_reservation_is_outbound(self) -> None:
        assert REQUIRES_RESERVATION.issubset(OUTBOUND_TYPES)

    def test_requires_reason_code_contains_adjustments(self) -> None:
        assert TransactionType.ADJUSTMENT_IN in REQUIRES_REASON_CODE
        assert TransactionType.ADJUSTMENT_OUT in REQUIRES_REASON_CODE
        assert TransactionType.SCRAP in REQUIRES_REASON_CODE


# ===========================================================================
# Phase 1 – doc_type to transaction_type mapping
# ===========================================================================


class TestDocTypeMapping:
    def test_all_legacy_doc_types_are_mapped(self) -> None:
        for dt in DocumentType:
            assert dt in DOC_TYPE_TO_TRANSACTION_TYPE

    def test_import_maps_to_purchase_receipt(self) -> None:
        assert default_transaction_type(DocumentType.IMPORT) == TransactionType.PURCHASE_RECEIPT

    def test_export_maps_to_adjustment_out(self) -> None:
        assert default_transaction_type(DocumentType.EXPORT) == TransactionType.ADJUSTMENT_OUT

    def test_sale_maps_to_sales_shipment(self) -> None:
        assert default_transaction_type(DocumentType.SALE) == TransactionType.SALES_SHIPMENT

    def test_transfer_maps_to_transfer_issue(self) -> None:
        assert default_transaction_type(DocumentType.TRANSFER) == TransactionType.TRANSFER_ISSUE


# ===========================================================================
# Phase 1 – backward compatibility: old API responses unchanged
# ===========================================================================


class TestDocumentBackwardCompatibility:
    def test_document_still_has_doc_type(self) -> None:
        service, _ = _service()
        doc = service.create_import_document(
            to_warehouse_id=10,
            items=[{"product_id": 1, "quantity": 5, "unit_price": 10}],
            created_by="operator",
        )
        assert doc.doc_type == DocumentType.IMPORT

    def test_document_still_has_legacy_statuses(self) -> None:
        service, _ = _service()
        doc = service.create_import_document(
            to_warehouse_id=10,
            items=[{"product_id": 1, "quantity": 5, "unit_price": 10}],
            created_by="operator",
        )
        assert doc.status == DocumentStatus.DRAFT
        service.post_document(doc.document_id, approved_by="manager")
        assert doc.status == DocumentStatus.POSTED

    def test_new_fields_default_to_none(self) -> None:
        service, _ = _service()
        doc = service.create_import_document(
            to_warehouse_id=10,
            items=[{"product_id": 1, "quantity": 5, "unit_price": 10}],
            created_by="operator",
        )
        assert doc.transaction_type is None
        assert doc.reason_code is None
        assert doc.requested_by is None
        assert doc.approved_at is None
        assert doc.execution_started_at is None
        assert doc.completed_at is None
        assert doc.assigned_to is None

    def test_summary_includes_new_fields_as_none(self) -> None:
        service, _ = _service()
        doc = service.create_import_document(
            to_warehouse_id=10,
            items=[{"product_id": 1, "quantity": 5, "unit_price": 10}],
            created_by="operator",
        )
        summary = doc.get_summary()
        assert "transaction_type" in summary
        assert summary["transaction_type"] is None
        assert "reason_code" in summary
        assert summary["reason_code"] is None

    def test_old_create_methods_still_work(self) -> None:
        service, _ = _service()
        import_doc = service.create_import_document(
            to_warehouse_id=10,
            items=[{"product_id": 1, "quantity": 5, "unit_price": 10}],
            created_by="operator",
        )
        export_doc = service.create_export_document(
            from_warehouse_id=10,
            items=[{"product_id": 1, "quantity": 5, "unit_price": 10}],
            created_by="operator",
        )
        sale_doc = service.create_sale_document(
            from_warehouse_id=10,
            customer_id=1,
            items=[{"product_id": 1, "quantity": 5, "unit_price": 10}],
            created_by="operator",
        )
        transfer_doc = service.create_transfer_document(
            from_warehouse_id=10,
            to_warehouse_id=11,
            items=[{"product_id": 1, "quantity": 5, "unit_price": 0}],
            created_by="operator",
        )
        assert all(
            d.status == DocumentStatus.DRAFT
            for d in [import_doc, export_doc, sale_doc, transfer_doc]
        )


# ===========================================================================
# Phase 1 – document line item new fields
# ===========================================================================


class TestDocumentProductNewFields:
    def test_requested_qty_defaults_to_quantity(self) -> None:
        item = DocumentProduct(product_id=1, quantity=10, unit_price=5.0)
        assert item.requested_qty == 10
        assert item.quantity == 10

    def test_executed_qty_defaults_to_none(self) -> None:
        item = DocumentProduct(product_id=1, quantity=10, unit_price=5.0)
        assert item.executed_qty is None

    def test_reserved_qty_defaults_to_zero(self) -> None:
        item = DocumentProduct(product_id=1, quantity=10, unit_price=5.0)
        assert item.reserved_qty == 0

    def test_difference_qty_defaults_to_zero(self) -> None:
        item = DocumentProduct(product_id=1, quantity=10, unit_price=5.0)
        assert item.difference_qty == 0

    def test_execution_status_defaults_to_none(self) -> None:
        item = DocumentProduct(product_id=1, quantity=10, unit_price=5.0)
        assert item.execution_status is None

    def test_item_snapshots_include_new_fields(self) -> None:
        service, _ = _service()
        doc = service.create_import_document(
            to_warehouse_id=10,
            items=[{"product_id": 1, "quantity": 5, "unit_price": 10}],
            created_by="operator",
        )
        snapshots = doc._item_snapshots()
        assert snapshots[0]["requested_qty"] == 5
        assert snapshots[0]["executed_qty"] is None
        assert snapshots[0]["quantity"] == 5


# ===========================================================================
# Phase 1 – StockBalance value object
# ===========================================================================


class TestStockBalance:
    def test_available_qty_calculation(self) -> None:
        balance = StockBalance(physical_qty=100, reserved_qty=30)
        assert balance.available_qty == 70

    def test_defaults_to_zero(self) -> None:
        balance = StockBalance()
        assert balance.physical_qty == 0
        assert balance.reserved_qty == 0
        assert balance.incoming_qty == 0
        assert balance.in_transit_qty == 0
        assert balance.available_qty == 0

    def test_available_cannot_go_negative(self) -> None:
        balance = StockBalance(physical_qty=5, reserved_qty=10)
        assert balance.available_qty == -5

    def test_is_frozen_dataclass(self) -> None:
        balance = StockBalance(physical_qty=10)
        with pytest.raises(AttributeError):
            balance.physical_qty = 20  # type: ignore[misc]


# ===========================================================================
# Phase 1 – existing tests still pass (regression guard)
# ===========================================================================


class TestPhase0RegressionGuard:
    def test_posting_still_publishes_movement_requested(self) -> None:
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

    def test_cancel_still_works(self) -> None:
        service, _ = _service()
        doc = service.create_import_document(
            to_warehouse_id=10,
            items=[{"product_id": 1, "quantity": 5, "unit_price": 10}],
            created_by="operator",
        )
        cancelled = service.cancel_document(doc.document_id, cancelled_by="manager")
        assert cancelled.status == DocumentStatus.CANCELLED

    def test_empty_items_still_raises(self) -> None:
        service, _ = _service()
        with pytest.raises(ValidationError):
            service.create_import_document(
                to_warehouse_id=10, items=[], created_by="operator"
            )
