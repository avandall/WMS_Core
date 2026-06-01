from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.shared.domain.business_exceptions import ValidationError
from app.shared.domain.entity import DomainEntity
from app.modules.warehouses.domain.value_objects import BinCode, PositionType


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
        object.__setattr__(self, "code", BinCode(self.code).value)
        object.__setattr__(self, "type", PositionType(self.type).value)

    @property
    def identity(self) -> int:
        return self.id
