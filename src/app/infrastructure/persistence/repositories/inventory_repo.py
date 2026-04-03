from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.exceptions import (
    InvalidQuantityError,
    InsufficientStockError,
)
from app.domain.entities.inventory import InventoryItem
from app.core.transaction import TransactionalRepository
from app.domain.interfaces import IInventoryRepo
from app.infrastructure.persistence.models import InventoryModel


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

    def get_quantity(self, product_id: int) -> int:
        row = self.session.get(InventoryModel, product_id)
        return row.quantity if row else 0

    def get_all(self) -> List[InventoryItem]:
        rows = self.session.execute(select(InventoryModel)).scalars().all()
        return [self._to_domain(row) for row in rows]

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

    @staticmethod
    def _to_domain(row: InventoryModel) -> InventoryItem:
        return InventoryItem(product_id=row.product_id, quantity=row.quantity)
