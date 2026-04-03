from __future__ import annotations

from app.domain.exceptions import InsufficientStockError, InvalidIDError, InvalidQuantityError
from app.domain.interfaces.entity import DomainEntity


class InventoryItem(DomainEntity):
    """Domain entity for inventory items."""

    def __init__(self, product_id: int, quantity: int = 0) -> None:
        self._validate_product_id(product_id)
        self._validate_quantity(quantity)

        self.product_id = product_id
        self.quantity = quantity

    @staticmethod
    def _validate_product_id(product_id: int) -> None:
        if not isinstance(product_id, int) or product_id <= 0:
            raise InvalidIDError("product_id must be a positive integer")

    @staticmethod
    def _validate_quantity(quantity: int) -> None:
        if not isinstance(quantity, int) or quantity < 0:
            raise InvalidQuantityError("quantity must be a non-negative integer")

    def add_quantity(self, amount: int) -> None:
        if amount < 0:
            raise InvalidQuantityError("amount must be non-negative")
        new_quantity = self.quantity + amount
        self._validate_quantity(new_quantity)
        self.quantity = new_quantity

    def remove_quantity(self, amount: int) -> None:
        if amount < 0:
            raise InvalidQuantityError("amount must be non-negative")
        if amount > self.quantity:
            raise InsufficientStockError(
                f"Insufficient stock: available={self.quantity}, requested={amount}"
            )
        self.quantity -= amount

    def has_sufficient_stock(self, requested_quantity: int) -> bool:
        return self.quantity >= requested_quantity

    def is_empty(self) -> bool:
        return self.quantity == 0

    @property
    def identity(self) -> int:
        return self.product_id

    def __str__(self) -> str:
        return f"InventoryItem(product_id={self.product_id}, quantity={self.quantity})"

    def __repr__(self) -> str:
        return self.__str__()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, InventoryItem):
            return False
        return self.product_id == other.product_id

    def __hash__(self) -> int:
        return hash(self.product_id)
