import json
from datetime import datetime
from typing import Any, List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.shared.domain.business_exceptions import (
    InvalidQuantityError,
    InsufficientStockError,
)
from app.modules.inventory.domain.entities.inventory import InventoryItem
from app.shared.core.transaction import TransactionalRepository
from app.modules.inventory.domain.interfaces.inventory_repo import IInventoryRepo
from app.modules.inventory.infrastructure.models.inventory import InventoryModel
from app.modules.inventory.infrastructure.models.inventory_transaction import InventoryTransactionModel
from app.modules.inventory.infrastructure.models.movement_ledger import InventoryMovementLedgerModel
from app.modules.inventory.infrastructure.models.warehouse_inventory import WarehouseInventoryModel


class InventoryRepo(TransactionalRepository, IInventoryRepo):
    """PostgreSQL-backed repository for inventory management."""

    def __init__(self, session: Session):
        super().__init__(session)

    def save(self, inventory_item: InventoryItem) -> None:
        row = self.session.get(InventoryModel, inventory_item.product_id)
        if row:
            row.quantity = inventory_item.quantity
        else:
            row = InventoryModel(
                product_id=inventory_item.product_id, quantity=inventory_item.quantity
            )
            self.session.add(row)
        self._commit_if_auto()

    def add_quantity(self, product_id: int, quantity: int) -> None:
        row = self.session.get(InventoryModel, product_id)

        if quantity < 0:
            if row:
                # Adding negative to existing product
                raise InvalidQuantityError("Cannot add negative quantity")
            else:
                # Starting with negative inventory
                raise InvalidQuantityError(
                    f"Cannot start with negative inventory for {product_id}"
                )

        if row:
            row.quantity += quantity
        else:
            row = InventoryModel(product_id=product_id, quantity=quantity)
            self.session.add(row)
        self._commit_if_auto()

    def adjust_quantity(self, product_id: int, quantity_delta: int) -> None:
        if quantity_delta >= 0:
            self.add_quantity(product_id, quantity_delta)
            return
        self.remove_quantity(product_id, abs(quantity_delta))

    def adjust_warehouse_quantity(
        self, product_id: int, warehouse_id: int, quantity_delta: int
    ) -> None:
        row = self.session.execute(
            select(WarehouseInventoryModel).where(
                WarehouseInventoryModel.product_id == product_id,
                WarehouseInventoryModel.warehouse_id == warehouse_id,
            )
        ).scalar_one_or_none()

        if row is None:
            if quantity_delta < 0:
                raise InsufficientStockError(
                    f"Insufficient warehouse stock for product {product_id} in warehouse {warehouse_id}"
                )
            row = WarehouseInventoryModel(
                product_id=product_id,
                warehouse_id=warehouse_id,
                quantity=quantity_delta,
                # Phase 2: keep physical_qty in sync with quantity for new rows
                physical_qty=quantity_delta,
            )
            self.session.add(row)
        else:
            next_quantity = row.quantity + quantity_delta
            if next_quantity < 0:
                raise InsufficientStockError(
                    f"Insufficient warehouse stock. Available: {row.quantity}, Requested: {abs(quantity_delta)}"
                )
            row.quantity = next_quantity
            # Phase 2: keep physical_qty in sync with quantity on every update
            row.physical_qty = next_quantity
        self._commit_if_auto()

    def adjust_warehouse_in_transit(
        self, product_id: int, warehouse_id: int, quantity_delta: int
    ) -> None:
        row = self.session.execute(
            select(WarehouseInventoryModel).where(
                WarehouseInventoryModel.product_id == product_id,
                WarehouseInventoryModel.warehouse_id == warehouse_id,
            )
        ).scalar_one_or_none()

        if row is None:
            if quantity_delta < 0:
                raise InsufficientStockError(
                    f"Insufficient in-transit stock for product {product_id} in warehouse {warehouse_id}"
                )
            row = WarehouseInventoryModel(
                product_id=product_id,
                warehouse_id=warehouse_id,
                quantity=0,
                physical_qty=0,
                in_transit_qty=quantity_delta,
            )
            self.session.add(row)
        else:
            next_in_transit = row.in_transit_qty + quantity_delta
            if next_in_transit < 0:
                raise InsufficientStockError(
                    f"Insufficient in-transit stock. In-transit: {row.in_transit_qty}, Requested: {abs(quantity_delta)}"
                )
            row.in_transit_qty = next_in_transit
        self._commit_if_auto()

    def get_quantity(self, product_id: int) -> int:
        row = self.session.get(InventoryModel, product_id)
        return row.quantity if row else 0

    def get_all(self, limit: int = 0, offset: int = 0) -> List[InventoryItem]:
        query = select(InventoryModel).order_by(InventoryModel.product_id)
        if offset:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)
        rows = self.session.execute(query).scalars().all()
        return [self._to_domain(row) for row in rows]

    def get_inventory_by_warehouse_rows(self) -> list[dict]:
        rows = self.session.execute(
            select(WarehouseInventoryModel).order_by(
                WarehouseInventoryModel.warehouse_id,
                WarehouseInventoryModel.product_id,
            )
        ).scalars().all()
        return [
            {
                "product_id": int(row.product_id),
                "warehouse_id": int(row.warehouse_id),
                "warehouse_name": str(row.warehouse_id),
                "quantity": int(row.quantity),
                # Phase 3: Quantity matrix fields
                "physical_qty": int(row.physical_qty),
                "reserved_qty": int(row.reserved_qty),
                "incoming_qty": int(row.incoming_qty),
                "in_transit_qty": int(row.in_transit_qty),
                "available_qty": int(row.physical_qty - row.reserved_qty),
            }
            for row in rows
        ]

    def get_warehouse_distribution(self, product_id: int) -> list[dict]:
        rows = self.session.execute(
            select(WarehouseInventoryModel).where(
                WarehouseInventoryModel.product_id == product_id
            )
        ).scalars().all()
        return [
            {
                "warehouse_id": int(row.warehouse_id),
                "warehouse_name": str(row.warehouse_id),
                "quantity": int(row.quantity),
                # Phase 3: Quantity matrix fields
                "physical_qty": int(row.physical_qty),
                "reserved_qty": int(row.reserved_qty),
                "incoming_qty": int(row.incoming_qty),
                "in_transit_qty": int(row.in_transit_qty),
                "available_qty": int(row.physical_qty - row.reserved_qty),
            }
            for row in rows
        ]

    def get_warehouse_summary(self) -> dict[int, dict]:
        rows = self.session.execute(
            select(
                WarehouseInventoryModel.warehouse_id,
                func.count(WarehouseInventoryModel.product_id),
                func.coalesce(func.sum(WarehouseInventoryModel.quantity), 0),
            ).group_by(WarehouseInventoryModel.warehouse_id)
        ).all()
        return {
            int(warehouse_id): {
                "total_items": int(total_items),
                "unique_products": int(unique_products),
            }
            for warehouse_id, unique_products, total_items in rows
        }

    def delete(self, product_id: int) -> None:
        row = self.session.get(InventoryModel, product_id)
        if not row:
            return
        if row.quantity != 0:
            raise InvalidQuantityError("Cannot delete item with non-zero quantity")
        self.session.delete(row)
        self._commit_if_auto()

    def remove_quantity(self, product_id: int, quantity: int) -> None:
        row = self.session.get(InventoryModel, product_id)
        if not row:
            raise KeyError(f"Product {product_id} not found in inventory")
        if quantity < 0:
            raise InvalidQuantityError("Cannot remove negative quantity")
        if quantity > row.quantity:
            raise InsufficientStockError(
                f"Insufficient stock. Available: {row.quantity}, Requested: {quantity}"
            )
        row.quantity -= quantity
        self._commit_if_auto()

    def has_movement_event(self, event_id: str) -> bool:
        return self.session.get(InventoryMovementLedgerModel, event_id) is not None

    def record_movement_event(
        self,
        *,
        event_id: str,
        movement_type: str,
        document_id: int | None,
        payload: dict[str, Any],
    ) -> None:
        if self.has_movement_event(event_id):
            return
        self.session.add(
            InventoryMovementLedgerModel(
                event_id=event_id,
                movement_type=movement_type,
                document_id=document_id,
                payload_json=json.dumps(payload, sort_keys=True),
            )
        )
        self._commit_if_auto()

    @staticmethod
    def _to_domain(row: InventoryModel) -> InventoryItem:
        return InventoryItem(product_id=row.product_id, quantity=row.quantity)

    # Phase 4: Reservation methods
    def create_reservation(
        self,
        *,
        source_type: str,
        source_id: int | None,
        document_id: int | None,
        product_id: int,
        warehouse_id: int,
        requested_qty: int,
        created_by: str | None,
        idempotency_key: str | None,
        expires_at: datetime | None,
    ) -> int:
        from app.modules.inventory.infrastructure.models.stock_reservation import StockReservationModel

        # Check for idempotency
        if idempotency_key:
            existing = self.session.execute(
                select(StockReservationModel).where(StockReservationModel.idempotency_key == idempotency_key)
            ).scalar_one_or_none()
            if existing:
                return existing.id

        # Check ATP (available-to-promise)
        warehouse_row = self.session.execute(
            select(WarehouseInventoryModel).where(
                WarehouseInventoryModel.product_id == product_id,
                WarehouseInventoryModel.warehouse_id == warehouse_id,
            ).with_for_update()
        ).scalar_one_or_none()

        if not warehouse_row:
            raise InsufficientStockError(f"No inventory found for product {product_id} in warehouse {warehouse_id}")

        available_qty = warehouse_row.physical_qty - warehouse_row.reserved_qty
        if requested_qty > available_qty:
            raise InsufficientStockError(
                f"Insufficient available stock. Available: {available_qty}, Requested: {requested_qty}"
            )

        # Create reservation
        reservation = StockReservationModel(
            source_type=source_type,
            source_id=source_id,
            document_id=document_id,
            product_id=product_id,
            warehouse_id=warehouse_id,
            requested_qty=requested_qty,
            reserved_qty=requested_qty,
            status="RESERVED",
            created_by=created_by,
            idempotency_key=idempotency_key,
            expires_at=expires_at,
        )
        self.session.add(reservation)

        # Update warehouse reserved_qty
        warehouse_row.reserved_qty += requested_qty

        self.session.flush()
        self._commit_if_auto()
        return reservation.id

    def release_reservation(self, reservation_id: int, released_qty: int | None = None) -> None:
        from app.modules.inventory.infrastructure.models.stock_reservation import StockReservationModel

        reservation = self.session.get(StockReservationModel, reservation_id)
        if not reservation:
            raise KeyError(f"Reservation {reservation_id} not found")

        if reservation.status in ("RELEASED", "CONSUMED"):
            return  # Already released or consumed

        qty_to_release = released_qty or reservation.reserved_qty - reservation.released_qty
        if qty_to_release <= 0:
            return

        # Update reservation
        reservation.released_qty += qty_to_release
        reservation.reserved_qty -= qty_to_release
        if reservation.reserved_qty <= 0:
            reservation.status = "RELEASED"

        # Update warehouse reserved_qty
        warehouse_row = self.session.execute(
            select(WarehouseInventoryModel).where(
                WarehouseInventoryModel.product_id == reservation.product_id,
                WarehouseInventoryModel.warehouse_id == reservation.warehouse_id,
            ).with_for_update()
        ).scalar_one_or_none()

        if warehouse_row:
            warehouse_row.reserved_qty -= qty_to_release

        self._commit_if_auto()

    def consume_reservation(self, reservation_id: int, consumed_qty: int) -> None:
        from app.modules.inventory.infrastructure.models.stock_reservation import StockReservationModel

        reservation = self.session.get(StockReservationModel, reservation_id)
        if not reservation:
            raise KeyError(f"Reservation {reservation_id} not found")

        if consumed_qty > reservation.reserved_qty:
            raise InsufficientStockError(
                f"Cannot consume more than reserved. Reserved: {reservation.reserved_qty}, Requested: {consumed_qty}"
            )

        # Update reservation
        reservation.consumed_qty += consumed_qty
        reservation.reserved_qty -= consumed_qty
        reservation.released_qty += consumed_qty  # Consumed is also released from reservation

        if reservation.reserved_qty <= 0:
            reservation.status = "CONSUMED"

        # Update warehouse reserved_qty and physical_qty
        warehouse_row = self.session.execute(
            select(WarehouseInventoryModel).where(
                WarehouseInventoryModel.product_id == reservation.product_id,
                WarehouseInventoryModel.warehouse_id == reservation.warehouse_id,
            ).with_for_update()
        ).scalar_one_or_none()

        if warehouse_row:
            warehouse_row.reserved_qty -= consumed_qty
            warehouse_row.physical_qty -= consumed_qty  # Physical stock decreases on consumption
            warehouse_row.quantity = warehouse_row.physical_qty  # Keep legacy quantity in sync

        self._commit_if_auto()

    def get_reservation(self, reservation_id: int) -> dict | None:
        """Return reservation details as a plain dict, or None if not found."""
        from app.modules.inventory.infrastructure.models.stock_reservation import StockReservationModel
        row = self.session.get(StockReservationModel, reservation_id)
        if not row:
            return None
        return {
            "id": int(row.id),
            "product_id": int(row.product_id),
            "warehouse_id": int(row.warehouse_id),
            "document_id": int(row.document_id) if row.document_id else None,
            "reserved_qty": int(row.reserved_qty),
            "consumed_qty": int(row.consumed_qty),
            "released_qty": int(row.released_qty),
            "status": row.status,
        }

    def list_reservations(
        self, product_id: int | None = None, warehouse_id: int | None = None, status: str | None = None
    ) -> list[dict]:
        from app.modules.inventory.infrastructure.models.stock_reservation import StockReservationModel

        query = select(StockReservationModel)
        if product_id:
            query = query.where(StockReservationModel.product_id == product_id)
        if warehouse_id:
            query = query.where(StockReservationModel.warehouse_id == warehouse_id)
        if status:
            query = query.where(StockReservationModel.status == status)

        rows = self.session.execute(query.order_by(StockReservationModel.created_at.desc())).scalars().all()
        return [
            {
                "id": int(r.id),
                "source_type": r.source_type,
                "source_id": int(r.source_id) if r.source_id else None,
                "document_id": int(r.document_id) if r.document_id else None,
                "product_id": int(r.product_id),
                "warehouse_id": int(r.warehouse_id),
                "requested_qty": int(r.requested_qty),
                "reserved_qty": int(r.reserved_qty),
                "released_qty": int(r.released_qty),
                "consumed_qty": int(r.consumed_qty),
                "status": r.status,
                "expires_at": r.expires_at.isoformat() if r.expires_at else None,
                "created_by": r.created_by,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    def calculate_available_stock(self, product_id: int, warehouse_id: int) -> dict:
        warehouse_row = self.session.execute(
            select(WarehouseInventoryModel).where(
                WarehouseInventoryModel.product_id == product_id,
                WarehouseInventoryModel.warehouse_id == warehouse_id,
            )
        ).scalar_one_or_none()

        if not warehouse_row:
            return {
                "product_id": product_id,
                "warehouse_id": warehouse_id,
                "physical_qty": 0,
                "reserved_qty": 0,
                "available_qty": 0,
            }

        return {
            "product_id": product_id,
            "warehouse_id": warehouse_id,
            "physical_qty": int(warehouse_row.physical_qty),
            "reserved_qty": int(warehouse_row.reserved_qty),
            "available_qty": int(warehouse_row.physical_qty - warehouse_row.reserved_qty),
        }

    # Phase 9: Inventory transaction ledger methods
    def write_transaction(
        self,
        transaction_type: str,
        product_id: int,
        warehouse_id: int,
        quantity: int,
        physical_qty_before: Optional[int] = None,
        physical_qty_after: Optional[int] = None,
        reserved_qty_before: Optional[int] = None,
        reserved_qty_after: Optional[int] = None,
        available_qty_before: Optional[int] = None,
        available_qty_after: Optional[int] = None,
        document_id: Optional[int] = None,
        document_line_id: Optional[int] = None,
        user_id: Optional[str] = None,
        payload: Optional[dict] = None,
        idempotency_key: Optional[str] = None,
    ) -> dict:
        """Write an inventory transaction to the ledger with idempotency."""
        # Check for existing transaction with same idempotency key
        if idempotency_key:
            existing = self.session.execute(
                select(InventoryTransactionModel).where(
                    InventoryTransactionModel.idempotency_key == idempotency_key
                )
            ).scalar_one_or_none()
            if existing:
                # Return existing transaction (idempotent)
                return {
                    "id": int(existing.id),
                    "transaction_type": existing.transaction_type,
                    "document_id": int(existing.document_id) if existing.document_id else None,
                    "document_line_id": existing.document_line_id,
                    "product_id": int(existing.product_id),
                    "warehouse_id": int(existing.warehouse_id),
                    "quantity": int(existing.quantity),
                    "created_at": existing.created_at.isoformat() if existing.created_at else None,
                    "idempotency_key": existing.idempotency_key,
                }

        # Create new transaction
        transaction = InventoryTransactionModel(
            transaction_type=transaction_type,
            document_id=document_id,
            document_line_id=document_line_id,
            product_id=product_id,
            warehouse_id=warehouse_id,
            quantity=quantity,
            physical_qty_before=physical_qty_before,
            physical_qty_after=physical_qty_after,
            reserved_qty_before=reserved_qty_before,
            reserved_qty_after=reserved_qty_after,
            available_qty_before=available_qty_before,
            available_qty_after=available_qty_after,
            user_id=user_id,
            payload=json.dumps(payload) if payload else None,
            idempotency_key=idempotency_key,
        )
        self.session.add(transaction)
        self.session.flush()
        self._commit_if_auto()

        return {
            "id": int(transaction.id),
            "transaction_type": transaction.transaction_type,
            "document_id": int(transaction.document_id) if transaction.document_id else None,
            "document_line_id": transaction.document_line_id,
            "product_id": int(transaction.product_id),
            "warehouse_id": int(transaction.warehouse_id),
            "quantity": int(transaction.quantity),
            "created_at": transaction.created_at.isoformat() if transaction.created_at else None,
            "idempotency_key": transaction.idempotency_key,
        }

    def list_transactions(
        self,
        document_id: Optional[int] = None,
        product_id: Optional[int] = None,
        warehouse_id: Optional[int] = None,
        transaction_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[dict]:
        """List inventory transactions with optional filtering."""
        query = select(InventoryTransactionModel)
        
        if document_id:
            query = query.where(InventoryTransactionModel.document_id == document_id)
        if product_id:
            query = query.where(InventoryTransactionModel.product_id == product_id)
        if warehouse_id:
            query = query.where(InventoryTransactionModel.warehouse_id == warehouse_id)
        if transaction_type:
            query = query.where(InventoryTransactionModel.transaction_type == transaction_type)

        query = query.order_by(InventoryTransactionModel.created_at.desc())
        query = query.limit(limit).offset(offset)

        rows = self.session.execute(query).scalars().all()
        
        return [
            {
                "id": int(r.id),
                "transaction_type": r.transaction_type,
                "document_id": int(r.document_id) if r.document_id else None,
                "document_line_id": r.document_line_id,
                "product_id": int(r.product_id),
                "warehouse_id": int(r.warehouse_id),
                "quantity": int(r.quantity),
                "physical_qty_before": int(r.physical_qty_before) if r.physical_qty_before is not None else None,
                "physical_qty_after": int(r.physical_qty_after) if r.physical_qty_after is not None else None,
                "reserved_qty_before": int(r.reserved_qty_before) if r.reserved_qty_before is not None else None,
                "reserved_qty_after": int(r.reserved_qty_after) if r.reserved_qty_after is not None else None,
                "available_qty_before": int(r.available_qty_before) if r.available_qty_before is not None else None,
                "available_qty_after": int(r.available_qty_after) if r.available_qty_after is not None else None,
                "user_id": r.user_id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "payload": json.loads(r.payload) if r.payload else None,
                "idempotency_key": r.idempotency_key,
            }
            for r in rows
        ]
