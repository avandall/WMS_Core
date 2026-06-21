from __future__ import annotations

from dataclasses import dataclass

from app.shared.domain.business_exceptions import InvalidIDError, InvalidQuantityError, ValidationError


@dataclass(frozen=True)
class Quantity:
    value: int

    def __post_init__(self) -> None:
        if not isinstance(self.value, int) or self.value < 0:
            raise InvalidQuantityError("quantity must be a non-negative integer")


@dataclass(frozen=True)
class Sku:
    product_id: int

    def __post_init__(self) -> None:
        if not isinstance(self.product_id, int) or self.product_id <= 0:
            raise InvalidIDError("product_id must be a positive integer")


@dataclass(frozen=True)
class WarehouseLocation:
    warehouse_id: int

    def __post_init__(self) -> None:
        if not isinstance(self.warehouse_id, int) or self.warehouse_id <= 0:
            raise ValidationError("warehouse_id must be a positive integer")


@dataclass(frozen=True)
class StockBalance:
    physical_qty: int = 0
    reserved_qty: int = 0
    incoming_qty: int = 0
    in_transit_qty: int = 0

    @property
    def available_qty(self) -> int:
        return self.physical_qty - self.reserved_qty
