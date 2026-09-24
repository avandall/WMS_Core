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
from app.modules.inventory.infrastructure.models.inventory_location import InventoryLocationModel
from app.modules.inventory.infrastructure.models.inventory_transaction import InventoryTransactionModel
from app.modules.inventory.infrastructure.models.movement_ledger import InventoryMovementLedgerModel
from app.modules.inventory.infrastructure.models.position import PositionModel
from app.modules.inventory.infrastructure.models.stock_reservation import StockReservationModel
from app.modules.inventory.infrastructure.models.warehouse_inventory import WarehouseInventoryModel
from app.modules.inventory.infrastructure.models.draft_proposal import DraftProposalModel


class InventoryRepo(TransactionalRepository, IInventoryRepo):
    """PostgreSQL-backed repository for inventory management."""

    def __init__(self, session: Session):
        super().__init__(session)

    def save(self, inventory_item: InventoryItem) -> None:
        row = self.session.execute(
            select(WarehouseInventoryModel).where(
                WarehouseInventoryModel.product_id == inventory_item.product_id,
                WarehouseInventoryModel.warehouse_id == 1,
            ).with_for_update()
        ).scalar_one_or_none()
        if row:
            row.quantity = inventory_item.quantity
            row.physical_qty = inventory_item.quantity
        else:
            row = WarehouseInventoryModel(
                product_id=inventory_item.product_id,
                warehouse_id=1,
                quantity=inventory_item.quantity,
                physical_qty=inventory_item.quantity,
            )
            self.session.add(row)
        self._commit_if_auto()

    def add_quantity(self, product_id: int, quantity: int) -> None:
        if quantity < 0:
            raise InvalidQuantityError("Cannot add negative quantity")
        self.adjust_warehouse_quantity(product_id, 1, quantity)

    def adjust_warehouse_quantity(
        self, product_id: int, warehouse_id: int, quantity_delta: int
    ) -> None:
        row = self.session.execute(
            select(WarehouseInventoryModel).where(
                WarehouseInventoryModel.product_id == product_id,
                WarehouseInventoryModel.warehouse_id == warehouse_id,
            ).with_for_update()
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
            ).with_for_update()
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
        result = self.session.execute(
            select(func.coalesce(func.sum(WarehouseInventoryModel.physical_qty), 0)).where(
                WarehouseInventoryModel.product_id == product_id
            )
        ).scalar()
        return int(result or 0)

    def get_all(self, limit: int = 0, offset: int = 0) -> List[InventoryItem]:
        query = (
            select(
                WarehouseInventoryModel.product_id,
                func.coalesce(func.sum(WarehouseInventoryModel.physical_qty), 0).label("total_qty"),
            )
            .group_by(WarehouseInventoryModel.product_id)
            .order_by(WarehouseInventoryModel.product_id)
        )
        if offset:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)
        rows = self.session.execute(query).all()
        return [
            InventoryItem(product_id=int(product_id), quantity=int(total_qty))
            for product_id, total_qty in rows
        ]

    def get_low_stock_items(self, threshold: int = 10) -> List[InventoryItem]:
        """TASK-042 [EDGE-09]: Queries low stock items using SQL HAVING filter directly in DB."""
        query = (
            select(
                WarehouseInventoryModel.product_id,
                func.coalesce(func.sum(WarehouseInventoryModel.physical_qty), 0).label("total_qty"),
            )
            .group_by(WarehouseInventoryModel.product_id)
            .having(func.coalesce(func.sum(WarehouseInventoryModel.physical_qty), 0) <= threshold)
            .order_by(WarehouseInventoryModel.product_id)
        )
        rows = self.session.execute(query).all()
        return [
            InventoryItem(product_id=int(product_id), quantity=int(total_qty))
            for product_id, total_qty in rows
        ]

    def _get_warehouse_name_map(self, warehouse_ids: set[int]) -> dict[int, str]:
        """Resolves real warehouse names from DB warehouses table or gRPC Warehouse Service [BIZ-21]."""
        if not warehouse_ids:
            return {}
        name_map: dict[int, str] = {}
        try:
            from sqlalchemy import text
            ids_str = ",".join(str(int(w)) for w in warehouse_ids)
            stmt = text(f"SELECT warehouse_id, location FROM warehouses WHERE warehouse_id IN ({ids_str})")
            res = self.session.execute(stmt).fetchall()
            for wid, loc in res:
                if loc:
                    name_map[int(wid)] = str(loc)
        except Exception:
            pass

        missing_ids = warehouse_ids - set(name_map.keys())
        if missing_ids:
            import os
            wh_addr = os.getenv("WAREHOUSE_SERVICE_ADDR")
            if wh_addr:
                try:
                    import grpc
                    from shared_utils.security.grpc import configured_grpc_channel
                    from inventory_service.gen.wms.warehouse.v1 import warehouse_pb2, warehouse_pb2_grpc

                    with configured_grpc_channel(wh_addr) as channel:
                        stub = warehouse_pb2_grpc.WarehouseServiceStub(channel)
                        for wid in missing_ids:
                            try:
                                resp = stub.GetWarehouse(
                                    warehouse_pb2.GetWarehouseRequest(warehouse_id=wid),
                                    timeout=2.0,
                                )
                                if resp and (resp.name or resp.location):
                                    name_map[wid] = resp.name or resp.location
                            except grpc.RpcError:
                                pass
                except Exception:
                    pass

        for wid in warehouse_ids:
            if wid not in name_map:
                name_map[wid] = str(wid)

        return name_map

    def get_inventory_by_warehouse_rows(self) -> list[dict]:
        rows = self.session.execute(
            select(WarehouseInventoryModel).order_by(
                WarehouseInventoryModel.warehouse_id,
                WarehouseInventoryModel.product_id,
            )
        ).scalars().all()
        wh_ids = {int(row.warehouse_id) for row in rows}
        name_map = self._get_warehouse_name_map(wh_ids)
        return [
            {
                "product_id": int(row.product_id),
                "warehouse_id": int(row.warehouse_id),
                "warehouse_name": name_map.get(int(row.warehouse_id), str(row.warehouse_id)),
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
        wh_ids = {int(row.warehouse_id) for row in rows}
        name_map = self._get_warehouse_name_map(wh_ids)
        return [
            {
                "warehouse_id": int(row.warehouse_id),
                "warehouse_name": name_map.get(int(row.warehouse_id), str(row.warehouse_id)),
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
        total_qty = self.get_quantity(product_id)
        if total_qty != 0:
            raise InvalidQuantityError("Cannot delete item with non-zero quantity")
        rows = self.session.execute(
            select(WarehouseInventoryModel).where(
                WarehouseInventoryModel.product_id == product_id
            ).with_for_update()
        ).scalars().all()
        for row in rows:
            self.session.delete(row)
        self._commit_if_auto()

    def remove_quantity(self, product_id: int, quantity: int) -> None:
        if quantity < 0:
            raise InvalidQuantityError("Cannot remove negative quantity")
        total_qty = self.get_quantity(product_id)
        if total_qty == 0:
            raise KeyError(f"Product {product_id} not found in inventory")
        if quantity > total_qty:
            raise InsufficientStockError(
                f"Insufficient stock. Available: {total_qty}, Requested: {quantity}"
            )
        self.adjust_warehouse_quantity(product_id, 1, -quantity)

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
    def _to_domain(row: WarehouseInventoryModel) -> InventoryItem:
        return InventoryItem(product_id=row.product_id, quantity=row.physical_qty)

    def lock_warehouse_inventory_and_locations(self, pairs: list[tuple[int, int]]) -> None:
        """Lock InventoryLocationModel and WarehouseInventoryModel rows in sorted order to enforce Lock Ordering Rule."""
        unique_sorted_pairs = sorted(set(pairs))
        for product_id, warehouse_id in unique_sorted_pairs:
            self.session.execute(
                select(InventoryLocationModel).where(
                    InventoryLocationModel.warehouse_id == warehouse_id,
                    InventoryLocationModel.product_id == product_id,
                ).with_for_update()
            ).scalars().all()

            self.session.execute(
                select(WarehouseInventoryModel).where(
                    WarehouseInventoryModel.warehouse_id == warehouse_id,
                    WarehouseInventoryModel.product_id == product_id,
                ).with_for_update()
            ).scalars().all()

    def reserve_stock(
        self,
        product_id: int,
        warehouse_id: int,
        requested_qty: int,
        created_by: str | None = None,
        source_type: str = "SALE",
        document_id: int | None = None,
    ) -> int:
        """Helper to reserve stock for sales orders or other outbound processes."""
        return self.create_reservation(
            source_type=source_type,
            source_id=None,
            document_id=document_id,
            product_id=product_id,
            warehouse_id=warehouse_id,
            requested_qty=requested_qty,
            created_by=created_by,
            idempotency_key=None,
            expires_at=None,
        )

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

        # Step 1 (Lock Ordering): Lock WarehouseInventoryModel FIRST
        warehouse_row = self.session.execute(
            select(WarehouseInventoryModel).where(
                WarehouseInventoryModel.product_id == product_id,
                WarehouseInventoryModel.warehouse_id == warehouse_id,
            ).with_for_update()
        ).scalar_one_or_none()

        # Step 2 (Lock Ordering): Check idempotency on StockReservationModel SECOND with FOR UPDATE
        if idempotency_key:
            existing = self.session.execute(
                select(StockReservationModel)
                .where(StockReservationModel.idempotency_key == idempotency_key)
                .with_for_update()
            ).scalar_one_or_none()
            if existing:
                return existing.id

        if not warehouse_row:
            raise InsufficientStockError(f"No inventory found for product {product_id} in warehouse {warehouse_id}")

        # ATP Check: Only stock with status 'AVAILABLE' is available for sale reservations
        loc_available = self.session.execute(
            select(func.coalesce(func.sum(InventoryLocationModel.quantity - InventoryLocationModel.allocated_qty), 0))
            .where(
                InventoryLocationModel.warehouse_id == warehouse_id,
                InventoryLocationModel.product_id == product_id,
                InventoryLocationModel.status == "AVAILABLE",
            )
        ).scalar() or 0

        has_locations = self.session.execute(
            select(InventoryLocationModel.id)
            .where(
                InventoryLocationModel.warehouse_id == warehouse_id,
                InventoryLocationModel.product_id == product_id,
            ).limit(1)
        ).scalar() is not None

        if has_locations:
            available_qty = max(0, int(loc_available) - int(warehouse_row.reserved_qty))
        else:
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
        meta = self.session.execute(
            select(
                StockReservationModel.product_id,
                StockReservationModel.warehouse_id,
                StockReservationModel.status,
                StockReservationModel.reserved_qty,
            ).where(StockReservationModel.id == reservation_id)
        ).first()
        if not meta:
            raise KeyError(f"Reservation {reservation_id} not found")

        prod_id, wh_id, current_status, current_reserved_qty = meta
        if current_status in ("RELEASED", "CONSUMED") or current_reserved_qty == 0:
            return  # Already released, consumed, or zero reserved quantity

        # Step 1 (Lock Ordering): Lock WarehouseInventoryModel FIRST
        warehouse_row = self.session.execute(
            select(WarehouseInventoryModel).where(
                WarehouseInventoryModel.product_id == prod_id,
                WarehouseInventoryModel.warehouse_id == wh_id,
            ).with_for_update()
        ).scalar_one_or_none()

        # Step 2 (Lock Ordering): Lock StockReservationModel SECOND
        reservation = self.session.execute(
            select(StockReservationModel).where(StockReservationModel.id == reservation_id).with_for_update()
        ).scalar_one_or_none()
        if not reservation:
            raise KeyError(f"Reservation {reservation_id} not found")

        if reservation.status in ("RELEASED", "CONSUMED") or reservation.reserved_qty == 0:
            return  # Already released, consumed, or zero reserved quantity

        qty_to_release = released_qty if released_qty is not None else reservation.reserved_qty
        if qty_to_release <= 0:
            return

        # Update reservation
        reservation.released_qty += qty_to_release
        reservation.reserved_qty -= qty_to_release
        if reservation.reserved_qty <= 0:
            reservation.status = "RELEASED"

        if warehouse_row:
            warehouse_row.reserved_qty = max(0, warehouse_row.reserved_qty - qty_to_release)

        self._commit_if_auto()

    def consume_reservation(self, reservation_id: int, consumed_qty: int) -> None:
        meta = self.session.execute(
            select(
                StockReservationModel.product_id,
                StockReservationModel.warehouse_id,
            ).where(StockReservationModel.id == reservation_id)
        ).first()
        if not meta:
            raise KeyError(f"Reservation {reservation_id} not found")

        prod_id, wh_id = meta

        # Step 1 (Lock Ordering): Lock WarehouseInventoryModel FIRST
        warehouse_row = self.session.execute(
            select(WarehouseInventoryModel).where(
                WarehouseInventoryModel.product_id == prod_id,
                WarehouseInventoryModel.warehouse_id == wh_id,
            ).with_for_update()
        ).scalar_one_or_none()

        # Step 2 (Lock Ordering): Lock StockReservationModel SECOND
        reservation = self.session.execute(
            select(StockReservationModel).where(StockReservationModel.id == reservation_id).with_for_update()
        ).scalar_one_or_none()
        if not reservation:
            raise KeyError(f"Reservation {reservation_id} not found")

        if consumed_qty > reservation.reserved_qty:
            raise InsufficientStockError(
                f"Cannot consume more than reserved. Reserved: {reservation.reserved_qty}, Requested: {consumed_qty}"
            )

        # Update reservation: consumed_qty increases, reserved_qty decreases, released_qty remains UNCHANGED [BIZ-08 / TASK-032]
        reservation.consumed_qty += consumed_qty
        reservation.reserved_qty -= consumed_qty

        if reservation.reserved_qty <= 0:
            reservation.status = "CONSUMED"

        # Update warehouse reserved_qty and physical_qty
        if warehouse_row:
            warehouse_row.reserved_qty = max(0, warehouse_row.reserved_qty - consumed_qty)
            warehouse_row.physical_qty -= consumed_qty  # Physical stock decreases on consumption
            warehouse_row.quantity = warehouse_row.physical_qty  # Keep legacy quantity in sync

        self._commit_if_auto()

    def get_reservation(self, reservation_id: int) -> dict | None:
        """Return reservation details as a plain dict, or None if not found."""
        row = self.session.get(StockReservationModel, reservation_id)
        if not row:
            return None
        return {
            "id": int(row.id),
            "product_id": int(row.product_id),
            "warehouse_id": int(row.warehouse_id),
            "document_id": int(row.document_id) if row.document_id else None,
            "requested_qty": int(row.requested_qty),
            "reserved_qty": int(row.reserved_qty),
            "consumed_qty": int(row.consumed_qty),
            "released_qty": int(row.released_qty),
            "status": row.status,
        }

    def list_reservations(
        self,
        product_id: int | None = None,
        warehouse_id: int | None = None,
        status: str | None = None,
        document_id: int | None = None,
    ) -> list[dict]:

        query = select(StockReservationModel)
        if product_id:
            query = query.where(StockReservationModel.product_id == product_id)
        if warehouse_id:
            query = query.where(StockReservationModel.warehouse_id == warehouse_id)
        if status:
            query = query.where(StockReservationModel.status == status)
        if document_id:
            query = query.where(StockReservationModel.document_id == document_id)

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

        loc_available = self.session.execute(
            select(func.coalesce(func.sum(InventoryLocationModel.quantity - InventoryLocationModel.allocated_qty), 0))
            .where(
                InventoryLocationModel.warehouse_id == warehouse_id,
                InventoryLocationModel.product_id == product_id,
                InventoryLocationModel.status == "AVAILABLE",
            )
        ).scalar() or 0

        has_locations = self.session.execute(
            select(InventoryLocationModel.id)
            .where(
                InventoryLocationModel.warehouse_id == warehouse_id,
                InventoryLocationModel.product_id == product_id,
            ).limit(1)
        ).scalar() is not None

        calc_available = max(0, int(loc_available) - int(warehouse_row.reserved_qty)) if has_locations else int(warehouse_row.physical_qty - warehouse_row.reserved_qty)

        return {
            "product_id": product_id,
            "warehouse_id": warehouse_id,
            "physical_qty": int(warehouse_row.physical_qty),
            "reserved_qty": int(warehouse_row.reserved_qty),
            "available_qty": int(calc_available),
        }

    def get_availability(self, product_id: int, warehouse_id: int) -> dict:
        """Alias for calculate_available_stock."""
        return self.calculate_available_stock(product_id=product_id, warehouse_id=warehouse_id)

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

    def get_inventory_locations(
        self,
        warehouse_id: Optional[int] = None,
        product_id: Optional[int] = None,
        position_id: Optional[int] = None,
        lpn: Optional[str] = None,
        status: Optional[str] = None,
        lot_number: Optional[str] = None,
        owner_id: Optional[str] = None,
        for_update: bool = False,
    ) -> List[dict]:
        query = (
            select(InventoryLocationModel, PositionModel)
            .outerjoin(PositionModel, InventoryLocationModel.position_id == PositionModel.id)
        )
        if for_update:
            query = query.with_for_update(of=InventoryLocationModel)
        if warehouse_id is not None:
            query = query.where(InventoryLocationModel.warehouse_id == warehouse_id)
        if owner_id is not None:
            query = query.where(InventoryLocationModel.owner_id == owner_id)
        if product_id is not None:
            query = query.where(InventoryLocationModel.product_id == product_id)
        if position_id is not None:
            query = query.where(InventoryLocationModel.position_id == position_id)
        if lpn is not None:
            query = query.where(InventoryLocationModel.lpn == lpn)
        if status is not None:
            query = query.where(InventoryLocationModel.status == status)
        if lot_number is not None:
            query = query.where(InventoryLocationModel.lot_number == lot_number)

        query = query.order_by(
            InventoryLocationModel.warehouse_id,
            InventoryLocationModel.position_id,
            InventoryLocationModel.product_id,
        )
        results = self.session.execute(query).all()
        locations = []
        for loc, pos in results:
            locations.append({
                "id": int(loc.id),
                "warehouse_id": int(loc.warehouse_id),
                "owner_id": loc.owner_id or "DEFAULT_OWNER",
                "position_id": int(loc.position_id),
                "product_id": int(loc.product_id),
                "lpn": loc.lpn or "",
                "lot_number": loc.lot_number or "",
                "mfg_date": loc.mfg_date.isoformat() if loc.mfg_date else None,
                "expiry_date": loc.expiry_date.isoformat() if loc.expiry_date else None,
                "quantity": int(loc.quantity),
                "allocated_qty": int(loc.allocated_qty),
                "status": loc.status,
                "available_qty": int(loc.quantity - loc.allocated_qty),
                "x_coordinate": float(pos.x_coordinate or 0.0) if pos else 0.0,
                "y_coordinate": float(pos.y_coordinate or 0.0) if pos else 0.0,
                "z_coordinate": float(pos.z_coordinate or 0.0) if pos else 0.0,
                "zone_id": (pos.zone or "ZONE-A") if pos else "ZONE-A",
                "aisle": (pos.aisle or "AISLE-01") if pos else "AISLE-01",
                "bay": (pos.bay or "BAY-01") if pos else "BAY-01",
                "level": (pos.level or "1") if pos else "1",
                "location_code": (pos.code or f"POS-{loc.position_id}") if pos else f"POS-{loc.position_id}",
            })
        return locations

    def adjust_location_quantity(
        self,
        warehouse_id: int,
        position_id: int,
        product_id: int,
        quantity_delta: int,
        allocated_delta: int = 0,
        lpn: str = "",
        status: str = "AVAILABLE",
        lot_number: str = "",
        mfg_date: Optional[datetime] = None,
        expiry_date: Optional[datetime] = None,
        owner_id: str = "DEFAULT_OWNER",
    ) -> dict:
        lpn_clean = lpn or ""
        lot_clean = lot_number or ""
        owner_clean = owner_id or "DEFAULT_OWNER"
        row = self.session.execute(
            select(InventoryLocationModel).where(
                InventoryLocationModel.warehouse_id == warehouse_id,
                InventoryLocationModel.owner_id == owner_clean,
                InventoryLocationModel.position_id == position_id,
                InventoryLocationModel.product_id == product_id,
                InventoryLocationModel.lpn == lpn_clean,
                InventoryLocationModel.lot_number == lot_clean,
                InventoryLocationModel.status == status,
            ).with_for_update()
        ).scalar_one_or_none()

        if row is None:
            if quantity_delta < 0 or allocated_delta < 0:
                raise InsufficientStockError(
                    f"No inventory location found for warehouse={warehouse_id}, owner={owner_clean}, position={position_id}, product={product_id}, lpn={lpn_clean}, lot={lot_clean}"
                )
            new_qty = quantity_delta
            new_allocated = allocated_delta
            if new_allocated > new_qty:
                raise InvalidQuantityError("allocated_qty cannot exceed quantity")
            row = InventoryLocationModel(
                warehouse_id=warehouse_id,
                owner_id=owner_clean,
                position_id=position_id,
                product_id=product_id,
                lpn=lpn_clean,
                lot_number=lot_clean,
                mfg_date=mfg_date,
                expiry_date=expiry_date,
                quantity=new_qty,
                allocated_qty=new_allocated,
                status=status,
            )
            self.session.add(row)
        else:
            next_qty = row.quantity + quantity_delta
            next_allocated = row.allocated_qty + allocated_delta
            if next_qty < 0:
                raise InsufficientStockError(
                    f"Insufficient location stock: current={row.quantity}, delta={quantity_delta}"
                )
            if next_allocated < 0:
                raise InvalidQuantityError("allocated_qty cannot be negative")
            if next_allocated > next_qty:
                raise InvalidQuantityError("allocated_qty cannot exceed quantity")
            row.quantity = next_qty
            row.allocated_qty = next_allocated
            if mfg_date is not None:
                row.mfg_date = mfg_date
            if expiry_date is not None:
                row.expiry_date = expiry_date

        self.session.flush()
        # Sync warehouse_inventory summary Read-Model
        self.sync_warehouse_inventory_summary(warehouse_id, product_id, owner_clean)
        self._commit_if_auto()

        return {
            "id": int(row.id),
            "warehouse_id": int(row.warehouse_id),
            "owner_id": row.owner_id,
            "position_id": int(row.position_id),
            "product_id": int(row.product_id),
            "lpn": row.lpn,
            "lot_number": row.lot_number or "",
            "mfg_date": row.mfg_date.isoformat() if row.mfg_date else None,
            "expiry_date": row.expiry_date.isoformat() if row.expiry_date else None,
            "quantity": int(row.quantity),
            "allocated_qty": int(row.allocated_qty),
            "status": row.status,
            "available_qty": int(row.quantity - row.allocated_qty),
        }

    def recall_query(self, lot_number: str) -> dict:
        """Recall Query: Get all location bins storing lot_number and customer orders receiving it."""
        loc_rows = self.session.execute(
            select(InventoryLocationModel).where(
                InventoryLocationModel.lot_number == lot_number
            )
        ).scalars().all()
        locations = [
            {
                "id": int(r.id),
                "warehouse_id": int(r.warehouse_id),
                "position_id": int(r.position_id),
                "product_id": int(r.product_id),
                "lpn": r.lpn or "",
                "lot_number": r.lot_number or "",
                "mfg_date": r.mfg_date.isoformat() if r.mfg_date else None,
                "expiry_date": r.expiry_date.isoformat() if r.expiry_date else None,
                "quantity": int(r.quantity),
                "allocated_qty": int(r.allocated_qty),
                "status": r.status,
                "available_qty": int(r.quantity - r.allocated_qty),
            }
            for r in loc_rows
        ]

        customers = []
        try:
            candidate_doc_ids: set[int] = set()

            tx_doc_ids = self.session.execute(
                select(InventoryTransactionModel.document_id).where(
                    InventoryTransactionModel.document_id.isnot(None)
                )
            ).scalars().all()
            candidate_doc_ids.update(int(d) for d in tx_doc_ids if d)

            res_doc_ids = self.session.execute(
                select(StockReservationModel.document_id).where(
                    StockReservationModel.document_id.isnot(None)
                )
            ).scalars().all()
            candidate_doc_ids.update(int(d) for d in res_doc_ids if d)

            ledger_doc_ids = self.session.execute(
                select(InventoryMovementLedgerModel.document_id).where(
                    InventoryMovementLedgerModel.document_id.isnot(None)
                )
            ).scalars().all()
            candidate_doc_ids.update(int(d) for d in ledger_doc_ids if d)

            from inventory_service.grpc_client import get_documents_stub
            from inventory_service.gen.wms.documents.v1 import documents_pb2

            with get_documents_stub() as stub:
                try:
                    list_resp = stub.ListDocuments(documents_pb2.ListDocumentsRequest(page=1, page_size=100))
                    for doc in list_resp.documents:
                        if doc.document_id:
                            candidate_doc_ids.add(int(doc.document_id))
                except Exception:
                    pass

                for doc_id in sorted(candidate_doc_ids):
                    try:
                        doc = stub.GetDocument(documents_pb2.GetDocumentRequest(document_id=doc_id))
                        if not doc or not doc.document_id:
                            continue
                        for item in doc.items:
                            if getattr(item, "lot_number", "") == lot_number:
                                customers.append({
                                    "customer_id": int(doc.customer_id),
                                    "document_id": int(doc.document_id),
                                    "doc_type": str(doc.doc_type),
                                    "product_id": int(item.product_id),
                                    "quantity": int(item.quantity),
                                    "lot_number": str(item.lot_number or ""),
                                })
                    except Exception:
                        continue
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Recall query customer lookup via gRPC failed: %s", e)


        return {
            "lot_number": lot_number,
            "locations": locations,
            "customers": customers,
        }

    def _get_active_reserved_qty(self, warehouse_id: int, product_id: int) -> int:
        reserved_sum = self.session.execute(
            select(func.coalesce(func.sum(StockReservationModel.reserved_qty), 0)).where(
                StockReservationModel.warehouse_id == warehouse_id,
                StockReservationModel.product_id == product_id,
                StockReservationModel.status == "RESERVED",
            )
        ).scalar()
        return int(reserved_sum or 0)

    def sync_warehouse_inventory_summary(self, warehouse_id: int, product_id: int, owner_id: str = "DEFAULT_OWNER") -> None:
        owner_clean = owner_id or "DEFAULT_OWNER"
        total_physical = self.session.execute(
            select(func.coalesce(func.sum(InventoryLocationModel.quantity), 0)).where(
                InventoryLocationModel.warehouse_id == warehouse_id,
                InventoryLocationModel.owner_id == owner_clean,
                InventoryLocationModel.product_id == product_id,
            )
        ).scalar() or 0

        total_allocated_loc = self.session.execute(
            select(func.coalesce(func.sum(InventoryLocationModel.allocated_qty), 0)).where(
                InventoryLocationModel.warehouse_id == warehouse_id,
                InventoryLocationModel.owner_id == owner_clean,
                InventoryLocationModel.product_id == product_id,
            )
        ).scalar() or 0

        active_reserved = self._get_active_reserved_qty(warehouse_id, product_id)
        effective_reserved = max(int(total_allocated_loc), int(active_reserved))

        wh_inv = self.session.execute(
            select(WarehouseInventoryModel).where(
                WarehouseInventoryModel.warehouse_id == warehouse_id,
                WarehouseInventoryModel.owner_id == owner_clean,
                WarehouseInventoryModel.product_id == product_id,
            ).with_for_update()
        ).scalar_one_or_none()

        if wh_inv is None:
            wh_inv = WarehouseInventoryModel(
                warehouse_id=warehouse_id,
                owner_id=owner_clean,
                product_id=product_id,
                quantity=total_physical,
                physical_qty=total_physical,
                reserved_qty=effective_reserved,
                incoming_qty=0,
                in_transit_qty=0,
            )
            self.session.add(wh_inv)
        else:
            wh_inv.quantity = total_physical
            wh_inv.physical_qty = total_physical
            wh_inv.reserved_qty = effective_reserved
        self.session.flush()

    def get_draft_proposal(self, proposal_id: str) -> Optional[DraftProposalModel]:
        return self.session.execute(
            select(DraftProposalModel).where(DraftProposalModel.proposal_id == proposal_id).with_for_update()
        ).scalar_one_or_none()

    def list_draft_proposals(
        self,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[List[DraftProposalModel], int]:
        stmt = select(DraftProposalModel)
        count_stmt = select(func.count()).select_from(DraftProposalModel)
        if status:
            stmt = stmt.where(DraftProposalModel.status == status)
            count_stmt = count_stmt.where(DraftProposalModel.status == status)
        total = self.session.execute(count_stmt).scalar() or 0
        stmt = stmt.order_by(DraftProposalModel.created_at.desc()).limit(limit).offset(offset)
        items = list(self.session.execute(stmt).scalars().all())
        return items, total

    def save_draft_proposal(self, proposal: DraftProposalModel) -> DraftProposalModel:
        self.session.add(proposal)
        self._commit_if_auto()
        return proposal


