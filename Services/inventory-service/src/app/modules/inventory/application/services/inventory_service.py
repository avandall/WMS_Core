from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.shared.core.logging import get_logger
from app.modules.inventory.application.ports import (
    InventoryEventPublisher,
    NoopInventoryEventPublisher,
)
from app.modules.inventory.domain.entities.inventory import InventoryItem
from app.modules.inventory.domain.value_objects import Quantity, Sku, WarehouseLocation
from app.shared.domain.business_exceptions import InvalidQuantityError
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

    def _record_outbox_event(self, event_type: str, payload: dict[str, Any]) -> None:
        session = getattr(self.inventory_repo, "session", None)
        if session is not None:
            try:
                from shared_utils.outbox.models import record_outbox_event
                record_outbox_event(session, event_type=event_type, payload=payload)
            except Exception as exc:
                logger.warning(f"Failed to record outbox event: {exc}")

    def _write_transaction(self, **kwargs) -> dict:
        tx = self.inventory_repo.write_transaction(**kwargs)
        if not isinstance(tx, dict):
            tx = {
                "id": 0,
                "transaction_type": kwargs.get("transaction_type") or "UNKNOWN",
                "product_id": kwargs.get("product_id") or 0,
                "warehouse_id": kwargs.get("warehouse_id") or 0,
                "quantity": kwargs.get("quantity") or 0,
                "document_id": kwargs.get("document_id"),
                "document_line_id": kwargs.get("document_line_id"),
                "created_at": None,
                "idempotency_key": kwargs.get("idempotency_key"),
            }
        tx_payload = {
            "event_id": f"inventory:transaction:{tx['id']}",
            "entity_type": "inventory_transaction",
            "entity_id": tx["id"],
            "transaction_id": tx["id"],
            "transaction_type": tx["transaction_type"],
            "product_id": tx["product_id"],
            "warehouse_id": tx["warehouse_id"],
            "quantity": tx["quantity"],
            "document_id": tx["document_id"],
            "document_line_id": tx["document_line_id"],
            "created_at": tx["created_at"],
            "idempotency_key": tx["idempotency_key"],
            "user_id": kwargs.get("user_id") or "system",
        }
        self._record_outbox_event("InventoryTransactionRecorded", tx_payload)
        try:
            self.event_publisher.publish(
                event_type="InventoryTransactionRecorded",
                payload=tx_payload,
            )
        except Exception as exc:
            logger.warning(f"Direct publish of InventoryTransactionRecorded failed (outbox will retry): {exc}")
        return tx

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
        transaction_type: Optional[str] = None,
    ) -> bool:
        Sku(product_id)
        if quantity_delta == 0:
            raise InvalidQuantityError("quantity_delta must not be zero")
        if event_id and self.inventory_repo.has_movement_event(event_id):
            return False

        target_warehouse_id = warehouse_id if warehouse_id is not None else 1
        WarehouseLocation(target_warehouse_id)
        self.inventory_repo.adjust_warehouse_quantity(product_id, target_warehouse_id, quantity_delta)
        self._record_movement(
            event_id=event_id,
            movement_type="InventoryAdjusted",
            document_id=None,
            payload={
                "product_id": product_id,
                "warehouse_id": target_warehouse_id,
                "quantity_delta": quantity_delta,
                "reason": reason,
            },
        )
        # Phase 9: Write immutable ledger entry for every adjustment
        tx_type = transaction_type or ("ADJUSTMENT_IN" if quantity_delta > 0 else "ADJUSTMENT_OUT")
        self._write_transaction(
            transaction_type=tx_type,
            product_id=product_id,
            warehouse_id=target_warehouse_id,
            quantity=abs(quantity_delta),
            idempotency_key=f"{event_id}:adjustment" if event_id else None,
            payload={"reason": reason, "quantity_delta": quantity_delta},
        )
        event_payload = {
            "event_id": event_id,
            "entity_type": "inventory",
            "entity_id": product_id,
            "product_id": product_id,
            "warehouse_id": target_warehouse_id,
            "quantity_delta": quantity_delta,
            "reason": reason,
        }
        self._record_outbox_event("InventoryAdjusted", event_payload)
        self._commit_if_needed()
        self.event_publisher.publish(
            event_type="InventoryAdjusted",
            payload=event_payload,
        )
        return True

    def adjust_in_transit(
        self,
        *,
        product_id: int,
        quantity_delta: int,
        warehouse_id: int,
        event_id: Optional[str] = None,
        reason: str = "transfer_in_transit",
    ) -> bool:
        Sku(product_id)
        WarehouseLocation(warehouse_id)
        if quantity_delta == 0:
            raise InvalidQuantityError("quantity_delta must not be zero")
        if event_id and self.inventory_repo.has_movement_event(event_id):
            return False

        self.inventory_repo.adjust_warehouse_in_transit(product_id, warehouse_id, quantity_delta)
        self._record_movement(
            event_id=event_id,
            movement_type="InventoryInTransitAdjusted",
            document_id=None,
            payload={
                "product_id": product_id,
                "warehouse_id": warehouse_id,
                "quantity_delta": quantity_delta,
                "reason": reason,
            },
        )
        self._commit_if_needed()
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

        if event_id and self.inventory_repo.has_movement_event(event_id):
            from sqlalchemy import select
            from app.modules.inventory.infrastructure.models.stock_reservation import StockReservationModel
            existing = self.inventory_repo.session.execute(
                select(StockReservationModel).where(
                    StockReservationModel.idempotency_key == event_id
                ).with_for_update()
            ).scalar_one_or_none()
            if existing:
                return existing.id
            return 0

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
        # Phase 9: Write immutable ledger entry for reservation
        self._write_transaction(
            transaction_type="RESERVATION",
            product_id=product_id,
            warehouse_id=warehouse_id,
            quantity=requested.value,
            document_id=document_id,
            idempotency_key=f"{event_id}:reservation" if event_id else None,
            payload={
                "reservation_id": reservation_id,
                "source_type": source_type,
                "source_id": source_id,
            },
        )
        res_payload = {
            "event_id": event_id,
            "entity_type": "inventory",
            "entity_id": product_id,
            "product_id": product_id,
            "warehouse_id": warehouse_id,
            "quantity": requested.value,
            "reservation_id": reservation_id,
        }
        self._record_outbox_event("StockReserved", res_payload)
        self._commit_if_needed()
        self.event_publisher.publish(
            event_type="StockReserved",
            payload=res_payload,
        )
        return reservation_id
    def release_reservation(
        self,
        *,
        reservation_id: int,
        released_qty: Optional[int] = None,
        event_id: Optional[str] = None,
    ) -> bool:
        # Retrieve reservation details before release
        reservation = self.inventory_repo.get_reservation(reservation_id)
        if not reservation:
            raise KeyError(f"Reservation {reservation_id} not found")

        status = reservation.get("status")
        reserved_qty = reservation.get("reserved_qty", 0)
        already_released = reservation.get("released_qty", 0)
        remaining = reserved_qty - already_released
        qty = released_qty if released_qty is not None else remaining

        if status in ("RELEASED", "CONSUMED") or remaining <= 0 or qty <= 0:
            return True

        prod_id = reservation["product_id"]
        wh_id = reservation["warehouse_id"]
        doc_id = reservation["document_id"]

        # Phase 4: Use persistent reservation release
        self.inventory_repo.release_reservation(reservation_id, released_qty)

        # Record legacy movement event for backward compatibility
        self._record_movement(
            event_id=event_id,
            movement_type="ReservationReleased",
            document_id=None,
            payload={
                "reservation_id": reservation_id,
                "released_qty": qty,
            },
        )

        # Phase 9: Write immutable ledger entry for reservation release
        self._write_transaction(
            transaction_type="RESERVATION_RELEASE",
            product_id=prod_id,
            warehouse_id=wh_id,
            quantity=qty,
            document_id=doc_id,
            idempotency_key=f"{event_id}:release" if event_id else None,
            payload={"reservation_id": reservation_id, "released_qty": qty},
        )
        rel_payload = {
            "event_id": event_id,
            "entity_type": "inventory",
            "reservation_id": reservation_id,
            "released_qty": qty,
            "product_id": prod_id,
            "warehouse_id": wh_id,
            "document_id": doc_id,
        }
        self._record_outbox_event("ReservationReleased", rel_payload)
        self._commit_if_needed()
        self.event_publisher.publish(
            event_type="ReservationReleased",
            payload=rel_payload,
        )
        return True

    def apply_document_movement(self, payload: dict[str, Any]) -> bool:
        event_id = str(payload.get("event_id") or "")
        if not event_id:
            raise ValueError("Inventory movement payload requires event_id")

        doc_type = str(payload.get("doc_type") or "").upper()
        document_id = int(payload["document_id"]) if payload.get("document_id") is not None else None
        from_warehouse_id = payload.get("from_warehouse_id")
        to_warehouse_id = payload.get("to_warehouse_id")
        items = list(payload.get("items") or [])
        if not items:
            raise InvalidQuantityError("Inventory movement requires at least one item")

        # Lock target warehouse inventory & location rows FIRST in sorted order to enforce Lock Ordering Rule
        lock_pairs = set()
        for item in items:
            p_id = int(item["product_id"])
            if to_warehouse_id is not None:
                lock_pairs.add((p_id, int(to_warehouse_id)))
            if from_warehouse_id is not None:
                lock_pairs.add((p_id, int(from_warehouse_id)))

        if lock_pairs:
            self.inventory_repo.lock_warehouse_inventory_and_locations(sorted(lock_pairs))

        # Re-check idempotency AFTER acquiring locks to eliminate double deduction under concurrency
        if self.inventory_repo.has_movement_event(event_id):
            return False

        for item in items:
            product_id = int(item["product_id"])
            quantity = Quantity(int(item["quantity"])).value
            if doc_type == "IMPORT":
                self._apply_inbound(product_id, int(to_warehouse_id), quantity)
            elif doc_type == "SALES_RETURN":
                pos_id = item.get("position_id") or 1
                lpn_val = str(item.get("lpn") or "")
                lot_val = str(item.get("lot_number") or "")
                self._apply_inbound(
                    product_id,
                    int(to_warehouse_id),
                    quantity,
                    position_id=pos_id,
                    lpn=lpn_val,
                    status="QUARANTINED",
                    lot_number=lot_val,
                )
            elif doc_type in {"EXPORT", "SALE", "PURCHASE_RETURN"}:
                self._apply_outbound(product_id, int(from_warehouse_id), quantity)
            elif doc_type == "TRANSFER":
                from_pos = item.get("from_position_id") or item.get("position_id")
                to_pos = item.get("to_position_id") or item.get("position_id")
                from_lpn_val = str(item.get("from_lpn") or item.get("lpn") or "")
                to_lpn_val = str(item.get("to_lpn") or item.get("lpn") or "")
                lot_val = str(item.get("lot_number") or "")
                self._apply_outbound(product_id, int(from_warehouse_id), quantity, position_id=from_pos, lpn=from_lpn_val, lot_number=lot_val)
                self._apply_inbound(product_id, int(to_warehouse_id), quantity, total_delta=0, position_id=to_pos, lpn=to_lpn_val, lot_number=lot_val)
            else:
                raise ValueError(f"Unsupported document movement type: {doc_type}")

        self._record_movement(
            event_id=event_id,
            movement_type="InventoryMovementApplied",
            document_id=document_id,
            payload=payload,
        )
        # Phase 9: Write immutable ledger entries for every physical stock change
        _tx_type_map = {
            "IMPORT": "PURCHASE_RECEIPT",
            "EXPORT": "ADJUSTMENT_OUT",
            "SALE": "SALES_SHIPMENT",
            "TRANSFER": "TRANSFER_ISSUE",
            "PURCHASE_RETURN": "PURCHASE_RETURN_SHIPMENT",
            "SALES_RETURN": "SALES_RETURN_RECEIPT",
        }
        ledger_tx_type = _tx_type_map.get(doc_type, doc_type)
        for item in items:
            _product_id = int(item["product_id"])
            _quantity = int(item["quantity"])
            _wh_id = int(to_warehouse_id or from_warehouse_id or 0)
            self._write_transaction(
                transaction_type=ledger_tx_type,
                product_id=_product_id,
                warehouse_id=_wh_id,
                quantity=_quantity,
                document_id=document_id,
                idempotency_key=f"{event_id}:ledger:{_product_id}" if event_id else None,
                payload={"doc_type": doc_type, "item": item},
            )
        doc_mov_payload = {
            "event_id": f"{event_id}:applied",
            "source_event_id": event_id,
            "entity_type": "document",
            "entity_id": document_id,
            "document_id": document_id,
            "doc_type": doc_type,
            "from_warehouse_id": from_warehouse_id,
            "to_warehouse_id": to_warehouse_id,
            "items": items,
        }
        self._record_outbox_event("InventoryMovementApplied", doc_mov_payload)
        self._commit_if_needed()
        self.event_publisher.publish(
            event_type="InventoryMovementApplied",
            payload=doc_mov_payload,
        )
        return True

    def get_total_quantity(self, product_id: int) -> int:
        return self.inventory_repo.get_quantity(product_id)

    def get_inventory_status(self, product_id: int) -> Dict[str, Any]:
        total_quantity = self.inventory_repo.get_quantity(product_id)
        warehouse_distribution = self.inventory_repo.get_warehouse_distribution(product_id)
        total_allocated = sum(
            row.get("reserved_qty", 0) + row.get("allocated_qty", 0)
            for row in warehouse_distribution
        )

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
        rows = self.inventory_repo.get_inventory_by_warehouse_rows()
        grouped: Dict[int, List[Dict[str, Any]]] = {}
        for row in rows:
            pid = int(row["product_id"])
            if pid not in grouped:
                grouped[pid] = []
            wh_dist = {k: v for k, v in row.items() if k != "product_id"}
            grouped[pid].append(wh_dist)

        all_items = self.inventory_repo.get_all()
        for item in all_items:
            if item.product_id not in grouped:
                grouped[item.product_id] = []

        result = []
        for pid in sorted(grouped.keys()):
            wh_dist = grouped[pid]
            total_quantity = sum(row.get("physical_qty", row.get("quantity", 0)) for row in wh_dist)
            total_allocated = sum(
                row.get("reserved_qty", 0) + row.get("allocated_qty", 0)
                for row in wh_dist
            )
            unallocated_quantity = total_quantity - total_allocated
            result.append(
                {
                    "product_id": pid,
                    "total_quantity": total_quantity,
                    "allocated_quantity": total_allocated,
                    "unallocated_quantity": unallocated_quantity,
                    "warehouse_count": len(wh_dist),
                    "warehouse_distribution": wh_dist,
                }
            )
        return result

    def get_low_stock_products(self, threshold: int = 10) -> List[Dict[str, Any]]:
        if threshold < 0:
            raise InvalidQuantityError("Threshold must be non-negative")
        if hasattr(self.inventory_repo, "get_low_stock_items"):
            items = self.inventory_repo.get_low_stock_items(threshold=threshold)
        else:
            items = [item for item in self.inventory_repo.get_all() if item.quantity <= threshold]
        return [
            {
                "product_id": item.product_id,
                "current_quantity": item.quantity,
                "threshold": threshold,
                "needs_restock": True,
            }
            for item in items
        ]

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
                row.get("reserved_qty", 0) + row.get("allocated_qty", 0)
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
        position_id: Optional[int] = None,
        lpn: str = "",
        status: str = "AVAILABLE",
        lot_number: str = "",
    ) -> None:
        Sku(product_id)
        WarehouseLocation(warehouse_id)
        if position_id:
            self.adjust_location_inventory(
                warehouse_id=warehouse_id,
                position_id=position_id,
                product_id=product_id,
                quantity_delta=quantity,
                lpn=lpn,
                status=status,
                lot_number=lot_number,
            )
        else:
            self.inventory_repo.adjust_warehouse_quantity(product_id, warehouse_id, quantity)

    def _apply_outbound(
        self,
        product_id: int,
        warehouse_id: int,
        quantity: int,
        *,
        position_id: Optional[int] = None,
        lpn: str = "",
        status: str = "AVAILABLE",
        lot_number: str = "",
    ) -> None:
        Sku(product_id)
        WarehouseLocation(warehouse_id)
        if position_id:
            self.adjust_location_inventory(
                warehouse_id=warehouse_id,
                position_id=position_id,
                product_id=product_id,
                quantity_delta=-quantity,
                lpn=lpn,
                status=status,
                lot_number=lot_number,
            )
        else:
            self.inventory_repo.adjust_warehouse_quantity(product_id, warehouse_id, -quantity)

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

    # Phase 10: Consume reservation
    def consume_reservation(
        self,
        *,
        reservation_id: int,
        consumed_qty: int,
        event_id: Optional[str] = None,
    ) -> bool:
        """Consumes a persistent reservation and updates physical stock."""
        self.inventory_repo.consume_reservation(reservation_id, consumed_qty)

        # Record legacy movement event for backward compatibility
        self._record_movement(
            event_id=event_id,
            movement_type="ReservationConsumed",
            document_id=None,
            payload={
                "reservation_id": reservation_id,
                "consumed_qty": consumed_qty,
            },
        )

        # Phase 9: Write immutable ledger entry for reservation consumption
        reservation = self.inventory_repo.get_reservation(reservation_id)
        prod_id = reservation["product_id"] if reservation else 0
        wh_id = reservation["warehouse_id"] if reservation else 0
        doc_id = reservation["document_id"] if reservation else None

        self._write_transaction(
            transaction_type="RESERVATION_CONSUME",
            product_id=prod_id,
            warehouse_id=wh_id,
            quantity=consumed_qty,
            document_id=doc_id,
            idempotency_key=f"{event_id}:consume" if event_id else None,
            payload={"reservation_id": reservation_id, "consumed_qty": consumed_qty},
        )
        con_payload = {
            "event_id": event_id,
            "entity_type": "inventory",
            "reservation_id": reservation_id,
            "consumed_qty": consumed_qty,
            "product_id": prod_id,
            "warehouse_id": wh_id,
            "document_id": doc_id,
        }
        self._record_outbox_event("ReservationConsumed", con_payload)
        self._commit_if_needed()
        self.event_publisher.publish(
            event_type="ReservationConsumed",
            payload=con_payload,
        )
        return True

    # Phase 10: Confirm inventory transaction
    def confirm_inventory_transaction(
        self,
        *,
        transaction_type: str,
        product_id: int,
        warehouse_id: int,
        quantity: int,
        reservation_id: int = 0,
        user_id: str = "system",
        idempotency_key: Optional[str] = None,
        source_warehouse_id: int = 0,
        position_id: int = 0,
        lpn: str = "",
        lot_number: str = "",
    ) -> int:
        """Confirms an inventory transaction (either consuming a reservation or directly updating stock)."""
        if quantity <= 0:
            raise InvalidQuantityError("Quantity must be positive")

        # Phase 15: Extract document_id from idempotency_key for rich events
        document_id = None
        if idempotency_key:
            parts = idempotency_key.split("_")
            if len(parts) >= 2 and parts[0] == "confirm":
                try:
                    document_id = int(parts[1])
                except ValueError:
                    pass

        if reservation_id > 0:
            self.consume_reservation(
                reservation_id=reservation_id,
                consumed_qty=quantity,
                event_id=idempotency_key,
            )
            # Fetch last transaction to return its ID
            txs = self.inventory_repo.list_transactions(
                product_id=product_id,
                warehouse_id=warehouse_id,
                transaction_type="RESERVATION_CONSUME",
                limit=1,
            )
            return txs[0]["id"] if txs else 0
        else:
            # Handle Transfer lifecycle stock movements
            if transaction_type == "TRANSFER_ISSUE":
                # TRANSFER_ISSUE reduces physical stock at source, increases in_transit stock at source
                if position_id > 0:
                    self.adjust_location_inventory(
                        warehouse_id=warehouse_id,
                        position_id=position_id,
                        product_id=product_id,
                        quantity_delta=-quantity,
                        lpn=lpn,
                        lot_number=lot_number,
                    )
                    self._write_transaction(
                        transaction_type="TRANSFER_ISSUE",
                        product_id=product_id,
                        warehouse_id=warehouse_id,
                        quantity=quantity,
                        document_id=document_id,
                        idempotency_key=f"{idempotency_key}:ledger" if idempotency_key else None,
                        payload={"position_id": position_id, "lpn": lpn, "lot_number": lot_number},
                    )
                else:
                    self.adjust_inventory(
                        product_id=product_id,
                        quantity_delta=-quantity,
                        warehouse_id=warehouse_id,
                        event_id=idempotency_key,
                        reason=f"confirm_issue_{document_id or 'transfer'}",
                        transaction_type="TRANSFER_ISSUE",
                    )
                self.adjust_in_transit(
                    product_id=product_id,
                    quantity_delta=quantity,
                    warehouse_id=warehouse_id,
                    event_id=f"{idempotency_key}:in_transit" if idempotency_key else None,
                    reason="transfer_issue_in_transit",
                )
                # Phase 15: Publish TransferIssued event
                issue_payload = {
                    "event_id": f"inventory:transfer-issue:{idempotency_key}" if idempotency_key else None,
                    "entity_type": "document",
                    "entity_id": document_id,
                    "document_id": document_id,
                    "product_id": product_id,
                    "warehouse_id": warehouse_id,
                    "quantity": quantity,
                    "user_id": user_id,
                }
                self._record_outbox_event("TransferIssued", issue_payload)
                self._commit_if_needed()
                self.event_publisher.publish(
                    event_type="TransferIssued",
                    payload=issue_payload,
                )
            elif transaction_type == "TRANSFER_RECEIPT":
                # TRANSFER_RECEIPT increases physical stock at destination, reduces in_transit stock at source
                if position_id > 0:
                    self.adjust_location_inventory(
                        warehouse_id=warehouse_id,
                        position_id=position_id,
                        product_id=product_id,
                        quantity_delta=quantity,
                        lpn=lpn,
                        lot_number=lot_number,
                    )
                    self._write_transaction(
                        transaction_type="TRANSFER_RECEIPT",
                        product_id=product_id,
                        warehouse_id=warehouse_id,
                        quantity=quantity,
                        document_id=document_id,
                        idempotency_key=f"{idempotency_key}:ledger" if idempotency_key else None,
                        payload={"source_warehouse_id": source_warehouse_id, "position_id": position_id, "lpn": lpn, "lot_number": lot_number},
                    )
                else:
                    self.adjust_inventory(
                        product_id=product_id,
                        quantity_delta=quantity,
                        warehouse_id=warehouse_id,
                        event_id=idempotency_key,
                        reason=f"confirm_receipt_{document_id or 'transfer'}",
                        transaction_type="TRANSFER_RECEIPT",
                    )
                # Decrement in-transit stock at the source warehouse
                src_wh = source_warehouse_id if source_warehouse_id > 0 else warehouse_id
                self.adjust_in_transit(
                    product_id=product_id,
                    quantity_delta=-quantity,
                    warehouse_id=src_wh,
                    event_id=f"{idempotency_key}:in_transit" if idempotency_key else None,
                    reason="transfer_receipt_in_transit",
                )
                # Phase 15: Publish TransferReceived event
                rcpt_payload = {
                    "event_id": f"inventory:transfer-receipt:{idempotency_key}" if idempotency_key else None,
                    "entity_type": "document",
                    "entity_id": document_id,
                    "document_id": document_id,
                    "product_id": product_id,
                    "warehouse_id": warehouse_id,
                    "source_warehouse_id": src_wh,
                    "quantity": quantity,
                    "user_id": user_id,
                }
                self._record_outbox_event("TransferReceived", rcpt_payload)
                self._commit_if_needed()
                self.event_publisher.publish(
                    event_type="TransferReceived",
                    payload=rcpt_payload,
                )
            elif transaction_type == "SALES_RETURN_RECEIPT":
                if position_id > 0:
                    self.adjust_location_inventory(
                        warehouse_id=warehouse_id,
                        position_id=position_id,
                        product_id=product_id,
                        quantity_delta=quantity,
                        lpn=lpn,
                        status="QUARANTINED",
                        lot_number=lot_number,
                    )
                    self._write_transaction(
                        transaction_type="SALES_RETURN_RECEIPT",
                        product_id=product_id,
                        warehouse_id=warehouse_id,
                        quantity=quantity,
                        document_id=document_id,
                        idempotency_key=f"{idempotency_key}:ledger" if idempotency_key else None,
                        payload={"position_id": position_id, "lpn": lpn, "lot_number": lot_number, "status": "QUARANTINED"},
                    )
                else:
                    self.adjust_inventory(
                        product_id=product_id,
                        quantity_delta=quantity,
                        warehouse_id=warehouse_id,
                        event_id=idempotency_key,
                        reason=f"confirm_sales_return_{document_id or 'return'}",
                        transaction_type="SALES_RETURN_RECEIPT",
                    )
            else:
                # Direct physical quantity adjustment
                OUTBOUND_TYPES = {
                    "SALES_SHIPMENT",
                    "PRODUCTION_ISSUE",
                    "PURCHASE_RETURN_SHIPMENT",
                    "TRANSFER_ISSUE",
                    "INTERNAL_CONSUMPTION",
                    "SCRAP",
                    "ADJUSTMENT_OUT"
                }
                is_outbound = transaction_type in OUTBOUND_TYPES
                delta = -quantity if is_outbound else quantity

                self.adjust_inventory(
                    product_id=product_id,
                    quantity_delta=delta,
                    warehouse_id=warehouse_id,
                    event_id=idempotency_key,
                    reason=f"direct_transaction_{transaction_type}",
                    transaction_type=transaction_type,
                )

            txs = self.inventory_repo.list_transactions(
                product_id=product_id,
                warehouse_id=warehouse_id,
                limit=1,
            )
            return txs[0]["id"] if txs else 0

    def get_inventory_locations(
        self,
        warehouse_id: Optional[int] = None,
        product_id: Optional[int] = None,
        position_id: Optional[int] = None,
        lpn: Optional[str] = None,
        status: Optional[str] = None,
        lot_number: Optional[str] = None,
        for_update: bool = False,
    ) -> List[dict]:
        return self.inventory_repo.get_inventory_locations(
            warehouse_id=warehouse_id,
            product_id=product_id,
            position_id=position_id,
            lpn=lpn,
            status=status,
            lot_number=lot_number,
            for_update=for_update,
        )

    def adjust_location_inventory(
        self,
        *,
        warehouse_id: int,
        position_id: int,
        product_id: int,
        quantity_delta: int,
        allocated_delta: int = 0,
        lpn: str = "",
        status: str = "AVAILABLE",
        lot_number: str = "",
        mfg_date: Optional[Any] = None,
        expiry_date: Optional[Any] = None,
    ) -> dict:
        return self.inventory_repo.adjust_location_quantity(
            warehouse_id=warehouse_id,
            position_id=position_id,
            product_id=product_id,
            quantity_delta=quantity_delta,
            allocated_delta=allocated_delta,
            lpn=lpn,
            status=status,
            lot_number=lot_number,
            mfg_date=mfg_date,
            expiry_date=expiry_date,
        )

    def allocate_fefo(
        self,
        *,
        warehouse_id: int,
        product_id: int,
        quantity: int,
        status: str = "AVAILABLE",
    ) -> List[dict]:
        from app.modules.inventory.application.services.allocation_service import AllocationService

        alloc_service = AllocationService(self.inventory_repo)
        return alloc_service.allocate_fefo(
            warehouse_id=warehouse_id,
            product_id=product_id,
            quantity=quantity,
            status=status,
        )

    def recall_query(self, lot_number: str) -> dict:
        from app.modules.inventory.application.services.allocation_service import AllocationService

        alloc_service = AllocationService(self.inventory_repo)
        return alloc_service.recall_query(lot_number)

    def _commit_if_needed(self) -> None:
        session = getattr(self.inventory_repo, "session", None)
        if session is not None:
            session.commit()


