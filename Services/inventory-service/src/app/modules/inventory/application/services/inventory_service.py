from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.shared.core.logging import get_logger
from app.modules.inventory.application.ports import (
    InventoryEventPublisher,
    NoopInventoryEventPublisher,
)
from app.modules.inventory.domain.entities.inventory import InventoryItem
from app.modules.inventory.domain.value_objects import Quantity, Sku, WarehouseLocation
from app.shared.domain.business_exceptions import InsufficientStockError, InvalidQuantityError
from app.modules.inventory.domain.interfaces.inventory_repo import IInventoryRepo

logger = get_logger(__name__)


class InventoryService:
    """Application service for inventory orchestration."""

    def __init__(
        self,
        inventory_repo: IInventoryRepo,
        event_publisher: Optional[InventoryEventPublisher] = None,
    ):
        self.inventory_repo = inventory_repo
        self.event_publisher = event_publisher or NoopInventoryEventPublisher()

    def add_to_total_inventory(self, product_id: int, quantity: int) -> None:
        if quantity < 0:
            raise InvalidQuantityError("Cannot add negative quantity to inventory")
        self.adjust_inventory(product_id=product_id, quantity_delta=quantity)

    def remove_from_total_inventory(self, product_id: int, quantity: int) -> None:
        if quantity < 0:
            raise InvalidQuantityError("Cannot remove negative quantity from inventory")
        self.adjust_inventory(product_id=product_id, quantity_delta=-quantity)

    def adjust_inventory(
        self,
        *,
        product_id: int,
        quantity_delta: int,
        warehouse_id: Optional[int] = None,
        event_id: Optional[str] = None,
        reason: str = "manual_adjustment",
    ) -> bool:
        Sku(product_id)
        if quantity_delta == 0:
            raise InvalidQuantityError("quantity_delta must not be zero")
        if event_id and self.inventory_repo.has_movement_event(event_id):
            return False

        if warehouse_id is not None:
            WarehouseLocation(warehouse_id)
            self.inventory_repo.adjust_warehouse_quantity(product_id, warehouse_id, quantity_delta)
        self.inventory_repo.adjust_quantity(product_id, quantity_delta)
        self._record_movement(
            event_id=event_id,
            movement_type="InventoryAdjusted",
            document_id=None,
            payload={
                "product_id": product_id,
                "warehouse_id": warehouse_id,
                "quantity_delta": quantity_delta,
                "reason": reason,
            },
        )
        self._commit_if_needed()
        self.event_publisher.publish(
            event_type="InventoryAdjusted",
            payload={
                "event_id": event_id,
                "entity_type": "inventory",
                "entity_id": product_id,
                "product_id": product_id,
                "warehouse_id": warehouse_id,
                "quantity_delta": quantity_delta,
                "reason": reason,
            },
        )
        return True

    def reserve_stock(
        self,
        *,
        product_id: int,
        quantity: int,
        warehouse_id: Optional[int] = None,
        event_id: Optional[str] = None,
        source_type: str = "manual",
        source_id: Optional[int] = None,
        document_id: Optional[int] = None,
        created_by: Optional[str] = None,
        expires_at: Optional[str] = None,
    ) -> bool:
        from datetime import datetime

        Sku(product_id)
        requested = Quantity(quantity)
        
        if warehouse_id is None:
            raise ValueError("warehouse_id is required for reservation")
        
        # Phase 4: Use persistent reservation with idempotency
        try:
            expires_dt = datetime.fromisoformat(expires_at) if expires_at else None
        except (ValueError, TypeError):
            expires_dt = None

        reservation_id = self.inventory_repo.create_reservation(
            source_type=source_type,
            source_id=source_id,
            document_id=document_id,
            product_id=product_id,
            warehouse_id=warehouse_id,
            requested_qty=requested.value,
            created_by=created_by,
            idempotency_key=event_id,  # Use event_id as idempotency key
            expires_at=expires_dt,
        )

        # Record legacy movement event for backward compatibility
        self._record_movement(
            event_id=event_id,
            movement_type="StockReserved",
            document_id=document_id,
            payload={
                "product_id": product_id,
                "warehouse_id": warehouse_id,
                "quantity": requested.value,
                "reservation_id": reservation_id,
            },
        )
        self._commit_if_needed()
        self.event_publisher.publish(
            event_type="StockReserved",
            payload={
                "event_id": event_id,
                "entity_type": "inventory",
                "entity_id": product_id,
                "product_id": product_id,
                "warehouse_id": warehouse_id,
                "quantity": requested.value,
                "reservation_id": reservation_id,
            },
        )
        return True

    def release_reservation(
        self,
        *,
        reservation_id: int,
        released_qty: Optional[int] = None,
        event_id: Optional[str] = None,
    ) -> bool:
        # Phase 4: Use persistent reservation release
        self.inventory_repo.release_reservation(reservation_id, released_qty)

        # Record legacy movement event for backward compatibility
        self._record_movement(
            event_id=event_id,
            movement_type="ReservationReleased",
            document_id=None,
            payload={
                "reservation_id": reservation_id,
                "released_qty": released_qty,
            },
        )
        self._commit_if_needed()
        self.event_publisher.publish(
            event_type="ReservationReleased",
            payload={
                "event_id": event_id,
                "entity_type": "inventory",
                "reservation_id": reservation_id,
                "released_qty": released_qty,
            },
        )
        return True

    def apply_document_movement(self, payload: dict[str, Any]) -> bool:
        event_id = str(payload.get("event_id") or "")
        if not event_id:
            raise ValueError("Inventory movement payload requires event_id")
        if self.inventory_repo.has_movement_event(event_id):
            return False

        doc_type = str(payload.get("doc_type") or "").upper()
        document_id = int(payload["document_id"]) if payload.get("document_id") is not None else None
        from_warehouse_id = payload.get("from_warehouse_id")
        to_warehouse_id = payload.get("to_warehouse_id")
        items = list(payload.get("items") or [])
        if not items:
            raise InvalidQuantityError("Inventory movement requires at least one item")

        for item in items:
            product_id = int(item["product_id"])
            quantity = Quantity(int(item["quantity"])).value
            if doc_type == "IMPORT":
                self._apply_inbound(product_id, int(to_warehouse_id), quantity)
            elif doc_type in {"EXPORT", "SALE"}:
                self._apply_outbound(product_id, int(from_warehouse_id), quantity)
            elif doc_type == "TRANSFER":
                self._apply_outbound(product_id, int(from_warehouse_id), quantity)
                self._apply_inbound(product_id, int(to_warehouse_id), quantity, total_delta=0)
            else:
                raise ValueError(f"Unsupported document movement type: {doc_type}")

        self._record_movement(
            event_id=event_id,
            movement_type="InventoryMovementApplied",
            document_id=document_id,
            payload=payload,
        )
        self._commit_if_needed()
        self.event_publisher.publish(
            event_type="InventoryMovementApplied",
            payload={
                "event_id": f"{event_id}:applied",
                "source_event_id": event_id,
                "entity_type": "document",
                "entity_id": document_id,
                "document_id": document_id,
                "doc_type": doc_type,
                "from_warehouse_id": from_warehouse_id,
                "to_warehouse_id": to_warehouse_id,
                "items": items,
            },
        )
        return True

    def get_total_quantity(self, product_id: int) -> int:
        return self.inventory_repo.get_quantity(product_id)

    def get_inventory_status(self, product_id: int) -> Dict[str, Any]:
        total_quantity = self.inventory_repo.get_quantity(product_id)
        warehouse_distribution = self.inventory_repo.get_warehouse_distribution(product_id)
        total_allocated = sum(row["quantity"] for row in warehouse_distribution)

        unallocated_quantity = total_quantity - total_allocated
        return {
            "product_id": product_id,
            "total_quantity": total_quantity,
            "allocated_quantity": total_allocated,
            "unallocated_quantity": unallocated_quantity,
            "warehouse_count": len(warehouse_distribution),
            "warehouse_distribution": warehouse_distribution,
        }

    def get_all_inventory_with_details(self) -> List[Dict[str, Any]]:
        all_inventory = self.inventory_repo.get_all()
        result = []
        for item in all_inventory:
            result.append(self.get_inventory_status(item.product_id))
        return result

    def get_low_stock_products(self, threshold: int = 10) -> List[Dict[str, Any]]:
        if threshold < 0:
            raise InvalidQuantityError("Threshold must be non-negative")
        low_stock_products = []
        for item in self.inventory_repo.get_all():
            if item.quantity <= threshold:
                low_stock_products.append(
                    {
                        "product_id": item.product_id,
                        "current_quantity": item.quantity,
                        "threshold": threshold,
                        "needs_restock": True,
                    }
                )
        return low_stock_products

    def get_all_inventory_items(self) -> List[InventoryItem]:
        return self.inventory_repo.get_all()

    def get_inventory_summary(self) -> Dict[str, Any]:
        all_inventory = self.inventory_repo.get_all()
        total_products = len(all_inventory)
        total_items = sum(item.quantity for item in all_inventory)

        return {
            "total_products": total_products,
            "total_inventory_items": total_items,
            "warehouse_summary": self.inventory_repo.get_warehouse_summary(),
            "low_stock_products": self.get_low_stock_products(),
        }

    def get_inventory_by_warehouse_rows(self) -> List[Dict[str, Any]]:
        """Return a flattened list of per-warehouse inventory rows.

        Shape is API-friendly and mirrors the legacy SQL join:
        - product_id
        - warehouse_id
        - warehouse_name (location)
        - quantity
        """

        rows = self.inventory_repo.get_inventory_by_warehouse_rows()
        rows.sort(key=lambda r: (r["warehouse_id"], r["product_id"]))
        return rows

    def validate_inventory_consistency(self) -> List[str]:
        issues = []
        for item in self.inventory_repo.get_all():
            total_allocated = sum(
                row["quantity"]
                for row in self.inventory_repo.get_warehouse_distribution(item.product_id)
            )
            if total_allocated > item.quantity:
                issues.append(
                    f"Inconsistency for product {item.product_id}: allocated {total_allocated} > total {item.quantity}"
                )
        return issues

    def _apply_inbound(
        self,
        product_id: int,
        warehouse_id: int,
        quantity: int,
        *,
        total_delta: Optional[int] = None,
    ) -> None:
        Sku(product_id)
        WarehouseLocation(warehouse_id)
        self.inventory_repo.adjust_warehouse_quantity(product_id, warehouse_id, quantity)
        self.inventory_repo.adjust_quantity(product_id, quantity if total_delta is None else total_delta)

    def _apply_outbound(self, product_id: int, warehouse_id: int, quantity: int) -> None:
        Sku(product_id)
        WarehouseLocation(warehouse_id)
        self.inventory_repo.adjust_warehouse_quantity(product_id, warehouse_id, -quantity)
        self.inventory_repo.adjust_quantity(product_id, -quantity)

    def _record_movement(
        self,
        *,
        event_id: Optional[str],
        movement_type: str,
        document_id: Optional[int],
        payload: dict[str, Any],
    ) -> None:
        if event_id:
            self.inventory_repo.record_movement_event(
                event_id=event_id,
                movement_type=movement_type,
                document_id=document_id,
                payload=payload,
            )

    def _commit_if_needed(self) -> None:
        session = getattr(self.inventory_repo, "session", None)
        if session is not None:
            session.commit()
