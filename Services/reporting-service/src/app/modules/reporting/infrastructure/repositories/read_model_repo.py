from __future__ import annotations

from typing import Any

from shared_utils.events import EventEnvelope
from sqlalchemy.orm import Session

from app.modules.reporting.infrastructure.models.projections import (
    DocumentSummary,
    InventorySummary,
    SalesSummary,
    WarehouseActivitySummary,
)
from app.modules.reporting.infrastructure.models.read_model_event import ReportingReadModelEvent


class ReportingReadModelRepo:
    def __init__(self, db: Session):
        self.db = db

    def record_event(self, *, stream_id: str, envelope: EventEnvelope) -> bool:
        existing = (
            self.db.query(ReportingReadModelEvent)
            .filter(ReportingReadModelEvent.event_id == envelope.event_id)
            .one_or_none()
        )
        if existing:
            return False

        payload = dict(envelope.payload)
        self.db.add(
            ReportingReadModelEvent(
                event_id=envelope.event_id,
                stream_id=stream_id,
                event_type=envelope.type,
                source=envelope.source,
                entity_type=payload.get("entity_type"),
                entity_id=str(payload["entity_id"]) if payload.get("entity_id") is not None else None,
                occurred_at=envelope.occurred_at,
                payload=payload,
            )
        )
        self._project(envelope)
        return True

    def inventory_report(self, *, warehouse_id: int | None = None, low_stock_threshold: int = 10) -> dict:
        rows = self.db.query(InventorySummary).order_by(InventorySummary.product_id).all()
        items = []
        for row in rows:
            warehouse_quantities = dict(row.warehouse_quantities or {})
            if warehouse_id is not None:
                quantity = int(warehouse_quantities.get(str(warehouse_id), 0))
            else:
                quantity = int(row.total_quantity)
            item = {
                "product_id": int(row.product_id),
                "quantity": quantity,
                "warehouse_quantities": warehouse_quantities,
                "updated_at": row.updated_at,
            }
            if warehouse_id is None or quantity > 0:
                items.append(item)
        return {
            "report_type": "inventory",
            "source": "reporting_projection",
            "warehouse_id": warehouse_id,
            "low_stock_threshold": low_stock_threshold,
            "items": items,
            "low_stock_items": [item for item in items if item["quantity"] <= low_stock_threshold],
        }

    def inventory_list(self) -> list[dict]:
        return self.inventory_report()["items"]

    def warehouse_report(self, *, warehouse_id: int | None = None) -> dict:
        query = self.db.query(WarehouseActivitySummary)
        if warehouse_id is not None:
            query = query.filter(WarehouseActivitySummary.warehouse_id == warehouse_id)
        rows = query.order_by(WarehouseActivitySummary.warehouse_id).all()
        return {
            "report_type": "warehouse",
            "source": "reporting_projection",
            "warehouse_id": warehouse_id,
            "items": [
                {
                    "warehouse_id": int(row.warehouse_id),
                    "movement_count": int(row.movement_count),
                    "total_quantity_delta": int(row.total_quantity_delta),
                    "last_document_id": row.last_document_id,
                    "updated_at": row.updated_at,
                }
                for row in rows
            ],
        }

    def documents_report(self) -> dict:
        rows = self.db.query(DocumentSummary).order_by(DocumentSummary.document_id).all()
        return {
            "report_type": "documents",
            "source": "reporting_projection",
            "documents": [self._document_row(row) for row in rows],
        }

    def product_report(self, *, product_id: int | None = None) -> dict:
        inventory = []
        if product_id is not None:
            row = self.db.get(InventorySummary, product_id)
            if row:
                inventory.append(
                    {
                        "product_id": int(row.product_id),
                        "quantity": int(row.total_quantity),
                        "warehouse_quantities": dict(row.warehouse_quantities or {}),
                    }
                )
        return {
            "report_type": "product",
            "source": "reporting_projection",
            "product_id": product_id,
            "items": inventory,
        }

    def sales_report(self, *, customer_id: int | None = None, salesperson: str | None = None) -> dict:
        _ = salesperson
        query = self.db.query(SalesSummary)
        if customer_id is not None:
            query = query.filter(SalesSummary.customer_id == customer_id)
        rows = query.order_by(SalesSummary.document_id).all()
        return {
            "report_type": "sales",
            "source": "reporting_projection",
            "customer_id": customer_id,
            "salesperson": salesperson,
            "items": [
                {
                    "document_id": int(row.document_id),
                    "customer_id": row.customer_id,
                    "status": row.status,
                    "total_quantity": int(row.total_quantity),
                    "total_value": float(row.total_value),
                }
                for row in rows
            ],
        }

    def _project(self, envelope: EventEnvelope) -> None:
        payload = dict(envelope.payload or {})
        if envelope.type == "DocumentUploaded":
            self._upsert_document(payload, status=str(payload.get("status") or "DRAFT"))
        elif envelope.type in ("DocumentPosted", "DocumentApproved", "WarehouseExecutionStarted", "DocumentCompleted", "StockReserved", "ReservationReleased"):
            status = payload.get("status")
            if not status:
                if envelope.type == "DocumentApproved":
                    status = "APPROVED"
                elif envelope.type == "WarehouseExecutionStarted":
                    status = "IN_PROGRESS"
                elif envelope.type == "DocumentCompleted":
                    status = "COMPLETED"
                elif envelope.type == "StockReserved":
                    status = "RESERVED"
                elif envelope.type == "ReservationReleased":
                    status = "COMPLETED"
                else:
                    status = "POSTED"
            self._mark_document_status(payload, status, posted_at=payload.get("posted_at"))
        elif envelope.type == "WarehouseExecutionConfirmed":
            document_id = int(payload["document_id"])
            items = list(payload.get("items") or [])
            executed_qty = sum(int(item.get("quantity") or 0) for item in items)
            row = self.db.get(DocumentSummary, document_id)
            if row:
                row.executed_quantity = executed_qty
                row.status = "EXECUTED"
                row.updated_at = _now()
                if row.doc_type == "SALE":
                    self._upsert_sale_from_document(row)
        elif envelope.type == "DocumentCancelled":
            self._mark_document_status(payload, "CANCELLED")
        elif envelope.type == "InventoryMovementApplied":
            self._apply_inventory_projection(payload)
        elif envelope.type == "InventoryAdjusted":
            self._apply_inventory_adjustment(payload)
        elif envelope.type == "InventoryTransactionRecorded":
            self._project_inventory_transaction(payload)

    def _update_matrix(
        self,
        product_id: int,
        warehouse_id: int,
        *,
        physical_delta: int = 0,
        reserved_delta: int = 0,
        in_transit_delta: int = 0,
        incoming_delta: int = 0,
    ) -> None:
        row = self.db.get(InventorySummary, product_id)
        if row is None:
            row = InventorySummary(
                product_id=product_id,
                total_quantity=0,
                warehouse_quantities={},
                warehouse_matrix={}
            )
            self.db.add(row)

        matrix = dict(row.warehouse_matrix or {})
        key = str(warehouse_id)
        if key not in matrix:
            matrix[key] = {
                "physical_qty": 0,
                "reserved_qty": 0,
                "incoming_qty": 0,
                "in_transit_qty": 0,
                "available_qty": 0,
            }

        m = matrix[key]
        m["physical_qty"] += physical_delta
        m["reserved_qty"] += reserved_delta
        m["in_transit_qty"] += in_transit_delta
        m["incoming_qty"] += incoming_delta
        m["available_qty"] = m["physical_qty"] - m["reserved_qty"]

        row.warehouse_matrix = matrix

        # Sync to backward compatible fields:
        row.warehouse_quantities = {
            wh: data["physical_qty"]
            for wh, data in matrix.items()
        }
        row.total_quantity = sum(data["physical_qty"] for data in matrix.values())
        row.updated_at = _now()

    def _project_inventory_transaction(self, payload: dict[str, Any]) -> None:
        tx_type = str(payload.get("transaction_type") or "").upper()
        product_id = int(payload.get("product_id") or 0)
        warehouse_id = int(payload.get("warehouse_id") or 0)
        quantity = int(payload.get("quantity") or 0)

        if not product_id or not warehouse_id:
            return

        OUTBOUND_TYPES = {
            "SALES_SHIPMENT",
            "PRODUCTION_ISSUE",
            "PURCHASE_RETURN_SHIPMENT",
            "INTERNAL_CONSUMPTION",
            "SCRAP",
            "ADJUSTMENT_OUT",
        }
        INBOUND_TYPES = {
            "PURCHASE_RECEIPT",
            "PRODUCTION_RECEIPT",
            "SALES_RETURN_RECEIPT",
            "ADJUSTMENT_IN",
        }

        if tx_type == "RESERVATION":
            self._update_matrix(product_id, warehouse_id, reserved_delta=quantity)
        elif tx_type == "RESERVATION_RELEASE":
            self._update_matrix(product_id, warehouse_id, reserved_delta=-quantity)
        elif tx_type == "RESERVATION_CONSUME":
            self._update_matrix(product_id, warehouse_id, physical_delta=-quantity, reserved_delta=-quantity)
            self._update_warehouse(warehouse_id, -quantity, payload.get("document_id"))
        elif tx_type == "TRANSFER_ISSUE":
            self._update_matrix(product_id, warehouse_id, physical_delta=-quantity, in_transit_delta=quantity)
            self._update_warehouse(warehouse_id, -quantity, payload.get("document_id"))
        elif tx_type == "TRANSFER_RECEIPT":
            self._update_matrix(product_id, warehouse_id, physical_delta=quantity)
            self._update_warehouse(warehouse_id, quantity, payload.get("document_id"))

            src_wh = int(payload.get("source_warehouse_id") or 0)
            if src_wh:
                self._update_matrix(product_id, src_wh, in_transit_delta=-quantity)
        elif tx_type in OUTBOUND_TYPES:
            self._update_matrix(product_id, warehouse_id, physical_delta=-quantity)
            self._update_warehouse(warehouse_id, -quantity, payload.get("document_id"))
        elif tx_type in INBOUND_TYPES:
            self._update_matrix(product_id, warehouse_id, physical_delta=quantity)
            self._update_warehouse(warehouse_id, quantity, payload.get("document_id"))

    def _upsert_document(self, payload: dict[str, Any], *, status: str) -> None:
        document_id = int(payload["document_id"])
        items = list(payload.get("items") or [])
        total_quantity = sum(int(item.get("quantity") or 0) for item in items)
        total_value = sum(
            int(item.get("quantity") or 0) * float(item.get("unit_price") or 0)
            for item in items
        )
        row = self.db.get(DocumentSummary, document_id)
        if row is None:
            row = DocumentSummary(document_id=document_id, doc_type=str(payload.get("doc_type") or ""), status=status)
            self.db.add(row)
        row.doc_type = str(payload.get("doc_type") or row.doc_type)
        row.status = status
        row.customer_id = payload.get("customer_id")
        row.from_warehouse_id = payload.get("from_warehouse_id")
        row.to_warehouse_id = payload.get("to_warehouse_id")
        row.total_quantity = total_quantity
        row.total_value = total_value
        row.created_at = payload.get("created_at")
        row.updated_at = _now()
        if row.doc_type == "SALE":
            self._upsert_sale_from_document(row)

    def _mark_document_status(
        self,
        payload: dict[str, Any],
        status: str,
        *,
        posted_at: str | None = None,
    ) -> None:
        document_id = int(payload["document_id"])
        row = self.db.get(DocumentSummary, document_id)
        if row is None:
            row = DocumentSummary(
                document_id=document_id,
                doc_type=str(payload.get("doc_type") or ""),
                status=status,
            )
            self.db.add(row)
        row.status = status
        if posted_at:
            row.posted_at = posted_at
        row.updated_at = _now()
        if row.doc_type == "SALE":
            self._upsert_sale_from_document(row)

    def _apply_inventory_projection(self, payload: dict[str, Any]) -> None:
        doc_type = str(payload.get("doc_type") or "").upper()
        document_id = int(payload["document_id"]) if payload.get("document_id") is not None else None
        for item in list(payload.get("items") or []):
            product_id = int(item["product_id"])
            quantity = int(item["quantity"])
            if doc_type == "IMPORT":
                self._update_inventory(product_id, quantity, payload.get("to_warehouse_id"))
                self._update_warehouse(payload.get("to_warehouse_id"), quantity, document_id)
            elif doc_type in {"EXPORT", "SALE"}:
                self._update_inventory(product_id, -quantity, payload.get("from_warehouse_id"))
                self._update_warehouse(payload.get("from_warehouse_id"), -quantity, document_id)
            elif doc_type == "TRANSFER":
                self._update_inventory(product_id, 0, payload.get("from_warehouse_id"), warehouse_delta=-quantity)
                self._update_inventory(product_id, 0, payload.get("to_warehouse_id"), warehouse_delta=quantity)
                self._update_warehouse(payload.get("from_warehouse_id"), -quantity, document_id)
                self._update_warehouse(payload.get("to_warehouse_id"), quantity, document_id)

    def _apply_inventory_adjustment(self, payload: dict[str, Any]) -> None:
        product_id = int(payload["product_id"])
        quantity_delta = int(payload["quantity_delta"])
        self._update_inventory(product_id, quantity_delta, payload.get("warehouse_id"))
        self._update_warehouse(payload.get("warehouse_id"), quantity_delta, None)

    def _update_inventory(
        self,
        product_id: int,
        total_delta: int,
        warehouse_id: Any,
        *,
        warehouse_delta: int | None = None,
    ) -> None:
        delta = total_delta if warehouse_delta is None else warehouse_delta
        if warehouse_id is not None:
            self._update_matrix(product_id, int(warehouse_id), physical_delta=delta)

    def _update_warehouse(self, warehouse_id: Any, quantity_delta: int, document_id: int | None) -> None:
        if warehouse_id is None:
            return
        row = self.db.get(WarehouseActivitySummary, int(warehouse_id))
        if row is None:
            row = WarehouseActivitySummary(warehouse_id=int(warehouse_id))
            self.db.add(row)
        row.movement_count = int(row.movement_count or 0) + 1
        row.total_quantity_delta = int(row.total_quantity_delta or 0) + int(quantity_delta)
        row.last_document_id = document_id
        row.updated_at = _now()

    def _upsert_sale_from_document(self, document: DocumentSummary) -> None:
        row = self.db.get(SalesSummary, document.document_id)
        if row is None:
            row = SalesSummary(document_id=document.document_id, status=document.status)
            self.db.add(row)
        row.customer_id = document.customer_id
        row.status = document.status
        row.total_quantity = document.total_quantity
        row.total_value = document.total_value
        row.updated_at = _now()

    @staticmethod
    def _document_row(row: DocumentSummary) -> dict[str, Any]:
        return {
            "document_id": int(row.document_id),
            "doc_type": row.doc_type,
            "status": row.status,
            "customer_id": row.customer_id,
            "from_warehouse_id": row.from_warehouse_id,
            "to_warehouse_id": row.to_warehouse_id,
            "total_quantity": int(row.total_quantity),
            "executed_quantity": int(row.executed_quantity or 0),
            "total_value": float(row.total_value),
            "created_at": row.created_at,
            "posted_at": row.posted_at,
        }


def _now():
    from datetime import datetime, timezone

    return datetime.now(tz=timezone.utc)
