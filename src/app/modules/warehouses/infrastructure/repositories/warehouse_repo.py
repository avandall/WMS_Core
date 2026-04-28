from typing import Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.shared.domain.business_exceptions import (
    InsufficientStockError,
    ValidationError,
    WarehouseNotFoundError,
)
from app.modules.inventory.domain.entities.inventory import InventoryItem
from app.modules.warehouses.domain.entities.warehouse import Warehouse
from app.shared.utils.infrastructure.id_generator import IDGenerator
from app.shared.core.transaction import TransactionalRepository
from app.shared.domain.warehouse_repo import IWarehouseRepo
from app.infrastructure.persistence.models import WarehouseInventoryModel, WarehouseModel


class WarehouseRepo(TransactionalRepository, IWarehouseRepo):
    """PostgreSQL-backed repository for warehouses and their inventory."""

    def __init__(self, session: Session):
        super().__init__(session)
        self._sync_id_generator()

    def _sync_id_generator(self) -> None:
        max_id = self.session.execute(
            select(func.max(WarehouseModel.warehouse_id))
        ).scalar()
        # Handle Mock objects in testing
        if hasattr(max_id, '__class__') and max_id.__class__.__name__ == 'Mock':
            start_id = 1
        else:
            start_id = (max_id or 0) + 1
        IDGenerator.reset_generator("warehouse", start_id)

    def create_warehouse(self, warehouse: Warehouse) -> None:
        model = WarehouseModel(
            warehouse_id=warehouse.warehouse_id, location=warehouse.location
        )
        self.session.add(model)
        self._commit_if_auto()

    def save(self, warehouse: Warehouse) -> None:
        existing = self.session.get(WarehouseModel, warehouse.warehouse_id)
        if existing:
            existing.location = warehouse.location
        else:
            self.create_warehouse(warehouse)
            existing = self.session.get(WarehouseModel, warehouse.warehouse_id)

        # Save inventory items to warehouse_inventory table
        # Delete existing inventory entries directly - O(1) operation
        from sqlalchemy import delete

        self.session.execute(
            delete(WarehouseInventoryModel).where(
                WarehouseInventoryModel.warehouse_id == warehouse.warehouse_id
            )
        )

        # Add new inventory items
        for item in warehouse.inventory:
            inv_model = WarehouseInventoryModel(
                warehouse_id=warehouse.warehouse_id,
                product_id=item.product_id,
                quantity=item.quantity,
            )
            self.session.add(inv_model)

        self._commit_if_auto()

    def get(self, warehouse_id: int) -> Optional[Warehouse]:
        model = self.session.get(WarehouseModel, warehouse_id)
        if not model:
            return None
        return self._to_domain(model)

    def get_all(self) -> Dict[int, Warehouse]:
        from sqlalchemy.orm import joinedload

        # Eager load inventory_items to prevent N+1 queries - O(1) instead of O(n+1)
        rows = (
            self.session.execute(
                select(WarehouseModel).options(
                    joinedload(WarehouseModel.inventory_items)
                )
            )
            .unique()
            .scalars()
            .all()
        )
        return {row.warehouse_id: self._to_domain(row) for row in rows}

    def delete(self, warehouse_id: int) -> None:
        model = self.session.get(WarehouseModel, warehouse_id)
        if model:
            try:
                self.session.delete(model)
                self._commit_if_auto()
            except Exception as exc:
                # Most commonly: FK references from historical documents.
                raise ValidationError(
                    f"Cannot delete warehouse {warehouse_id}: it is referenced by existing documents"
                ) from exc

    def get_warehouse_inventory(self, warehouse_id: int) -> List[InventoryItem]:
        warehouse = self.session.get(WarehouseModel, warehouse_id)
        if not warehouse:
            return []
        inventory_rows = self.session.execute(
            select(WarehouseInventoryModel).where(
                WarehouseInventoryModel.warehouse_id == warehouse_id
            )
        ).scalars()
        return [InventoryItem(row.product_id, row.quantity) for row in inventory_rows]

    def _get_pending_inventory_row(
        self, warehouse_id: int, product_id: int
    ) -> Optional[WarehouseInventoryModel]:
        # Session uses `autoflush=False`, so repeated operations in the same
        # transaction can create duplicate pending rows unless we check `session.new`.
        for obj in list(self.session.new) + list(self.session.dirty):
            if not isinstance(obj, WarehouseInventoryModel):
                continue
            if obj.warehouse_id == warehouse_id and obj.product_id == product_id:
                return obj
        return None

    def add_product_to_warehouse(
        self, warehouse_id: int, product_id: int, quantity: int
    ) -> None:
        warehouse = self.session.get(WarehouseModel, warehouse_id)
        if not warehouse:
            raise WarehouseNotFoundError(f"Warehouse {warehouse_id} not found")

        pending = self._get_pending_inventory_row(warehouse_id, product_id)
        if pending:
            pending.quantity += quantity
            self._commit_if_auto()
            return

        row = self.session.execute(
            select(WarehouseInventoryModel).where(
                WarehouseInventoryModel.warehouse_id == warehouse_id,
                WarehouseInventoryModel.product_id == product_id,
            )
        ).scalar_one_or_none()

        if row:
            row.quantity += quantity
        else:
            row = WarehouseInventoryModel(
                warehouse_id=warehouse_id, product_id=product_id, quantity=quantity
            )
            self.session.add(row)

        self._commit_if_auto()

    def remove_product_from_warehouse(
        self, warehouse_id: int, product_id: int, quantity: int
    ) -> None:
        warehouse = self.session.get(WarehouseModel, warehouse_id)
        if not warehouse:
            raise WarehouseNotFoundError(f"Warehouse {warehouse_id} not found")

        pending = self._get_pending_inventory_row(warehouse_id, product_id)
        if pending:
            if pending.quantity < quantity:
                raise InsufficientStockError(
                    f"Warehouse {warehouse_id} does not have enough product {product_id}"
                )
            pending.quantity -= quantity
            if pending.quantity == 0:
                # Not flushed yet; just remove pending row from the session.
                self.session.expunge(pending)
            self._commit_if_auto()
            return

        row = self.session.execute(
            select(WarehouseInventoryModel).where(
                WarehouseInventoryModel.warehouse_id == warehouse_id,
                WarehouseInventoryModel.product_id == product_id,
            )
        ).scalar_one_or_none()

        if not row or row.quantity < quantity:
            raise InsufficientStockError(
                f"Warehouse {warehouse_id} does not have enough product {product_id}"
            )

        row.quantity -= quantity
        if row.quantity == 0:
            self.session.delete(row)

        self._commit_if_auto()

    def _to_domain(self, model: WarehouseModel) -> Warehouse:
        inventory = [
            InventoryItem(row.product_id, row.quantity) for row in model.inventory_items
        ]
        return Warehouse(
            warehouse_id=model.warehouse_id,
            location=model.location,
            inventory=inventory,
        )
