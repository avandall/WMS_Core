from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.shared.domain.business_exceptions import ValidationError
from app.shared.domain.entity import DomainEntity


@dataclass(frozen=True)
class Position(DomainEntity):
    id: int
    warehouse_id: int
    code: str
    type: str
    description: Optional[str] = None
    is_active: bool = True

    def __post_init__(self) -> None:
        if self.warehouse_id <= 0:
            raise ValidationError("warehouse_id must be positive")
        if not self.code or not self.code.strip():
            raise ValidationError("position code is required")
        if len(self.code) > 50:
            raise ValidationError("position code must be at most 50 characters")
        if not self.type or not self.type.strip():
            raise ValidationError("position type is required")
        if len(self.type) > 20:
            raise ValidationError("position type must be at most 20 characters")

    @property
    def identity(self) -> int:
        return self.id


@dataclass(frozen=True)
class PositionInventoryItem:
    warehouse_id: int
    position_code: str
    product_id: int
    quantity: int
