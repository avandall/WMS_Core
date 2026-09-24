from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from app.shared.domain.business_exceptions import (
    InsufficientStockError,
    InvalidIDError,
    InvalidQuantityError,
)
from app.shared.domain.entity import DomainEntity


VALID_LOCATION_STATUSES = {"AVAILABLE", "ALLOCATED", "QUARANTINED", "DAMAGED", "REJECTED"}


@dataclass(slots=True)
class InventoryLocation(DomainEntity):
    """Domain entity for location-level inventory (Bin/Pallet/LPN level)."""

    id: int = 0
    warehouse_id: int = 0
    owner_id: str = "DEFAULT_OWNER"
    position_id: int = 0
    product_id: int = 0
    lpn: str = ""
    lot_number: str = ""
    mfg_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    quantity: int = 0
    allocated_qty: int = 0
    status: str = "AVAILABLE"
    created_at: Optional[datetime] = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if self.warehouse_id < 0:
            raise InvalidIDError("warehouse_id must be non-negative")
        if self.position_id < 0:
            raise InvalidIDError("position_id must be non-negative")
        if self.product_id < 0:
            raise InvalidIDError("product_id must be non-negative")
        if self.quantity < 0:
            raise InvalidQuantityError("quantity must be a non-negative integer")
        if self.allocated_qty < 0:
            raise InvalidQuantityError("allocated_qty must be a non-negative integer")
        if self.allocated_qty > self.quantity:
            raise InvalidQuantityError("allocated_qty cannot exceed total quantity")
        if self.status not in VALID_LOCATION_STATUSES:
            raise ValueError(f"Invalid status '{self.status}'. Must be one of {VALID_LOCATION_STATUSES}")

    @property
    def available_qty(self) -> int:
        return self.quantity - self.allocated_qty

    @property
    def identity(self) -> int:
        return self.id

    def add_stock(self, amount: int) -> None:
        if amount < 0:
            raise InvalidQuantityError("Amount must be non-negative")
        self.quantity += amount

    def remove_stock(self, amount: int) -> None:
        if amount < 0:
            raise InvalidQuantityError("Amount must be non-negative")
        if amount > self.available_qty:
            raise InsufficientStockError(
                f"Insufficient available stock at location: available={self.available_qty}, requested={amount}"
            )
        self.quantity -= amount

    def allocate_stock(self, amount: int) -> None:
        if amount < 0:
            raise InvalidQuantityError("Amount must be non-negative")
        if amount > self.available_qty:
            raise InsufficientStockError(
                f"Insufficient available stock to allocate: available={self.available_qty}, requested={amount}"
            )
        self.allocated_qty += amount

    def release_allocation(self, amount: int) -> None:
        if amount < 0:
            raise InvalidQuantityError("Amount must be non-negative")
        if amount > self.allocated_qty:
            raise InvalidQuantityError(
                f"Cannot release more than allocated quantity: allocated={self.allocated_qty}, requested={amount}"
            )
        self.allocated_qty -= amount

    def update_status(self, new_status: str) -> None:
        if new_status not in VALID_LOCATION_STATUSES:
            raise ValueError(f"Invalid status '{new_status}'")
        self.status = new_status
