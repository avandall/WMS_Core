from __future__ import annotations

from typing import Optional
from decimal import Decimal

from app.shared.domain.business_exceptions import InvalidIDError, InvalidQuantityError, ValidationError
from app.shared.domain.entity import DomainEntity


class Product(DomainEntity):
    """Domain entity for a product."""

    def __init__(
        self,
        product_id: int,
        name: str,
        description: Optional[str] = None,
        price: float = 0.0,
    ) -> None:
        self._validate_product_id(product_id)
        self._validate_name(name)
        self._validate_price(price)

        self.product_id = product_id
        self.name = name
        self.description = description
        self.price = float(price)

    @staticmethod
    def _validate_product_id(product_id: int) -> None:
        if not isinstance(product_id, int) or product_id <= 0:
            raise InvalidIDError("product_id must be a positive integer")

    @staticmethod
    def _validate_name(name: str) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValidationError("name must be a non-empty string")
        if len(name) > 100:
            raise ValidationError("name must be at most 100 characters")

    @staticmethod
    def _validate_price(price: float) -> None:
        if not isinstance(price, (int, float, Decimal)) or price < 0:
            raise InvalidQuantityError("price must be a non-negative number")

    def update_price(self, new_price: float) -> None:
        self._validate_price(new_price)
        self.price = float(new_price)

    def update_name(self, new_name: str) -> None:
        self._validate_name(new_name)
        self.name = new_name

    def update_description(self, new_description: Optional[str]) -> None:
        self.description = new_description

    def calculate_total_value(self, quantity: int) -> float:
        if not isinstance(quantity, int) or quantity < 0:
            raise InvalidQuantityError("quantity must be a non-negative integer")
        return self.price * quantity

    @property
    def identity(self) -> int:
        return self.product_id

    def __str__(self) -> str:
        return f"Product(id={self.product_id}, name='{self.name}', price={self.price})"

    def __repr__(self) -> str:
        return self.__str__()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Product):
            return False
        return self.product_id == other.product_id

    def __hash__(self) -> int:
        return hash(self.product_id)
