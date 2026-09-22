from __future__ import annotations

from dataclasses import dataclass

from app.shared.domain.business_exceptions import ValidationError
from app.shared.domain.entity import DomainEntity
from app.modules.warehouses.domain.value_objects import BinCode, PositionType, TemperatureZone


@dataclass(frozen=True)
class Position(DomainEntity):
    id: int
    warehouse_id: int
    code: str
    type: str
    description: str | None = None
    is_active: bool = True
    aisle: str | None = None
    bay: str | None = None
    level: str | None = None
    bin: str | None = None
    max_weight_kg: float | None = None
    temperature_zone: str = "ambient"
    pick_sequence: int = 0
    hazmat_class: str | None = None

    def __post_init__(self) -> None:
        if self.warehouse_id <= 0:
            raise ValidationError("warehouse_id must be positive")
        object.__setattr__(self, "code", BinCode(self.code).value)
        object.__setattr__(self, "type", PositionType(self.type).value)
        object.__setattr__(self, "temperature_zone", TemperatureZone(self.temperature_zone).value)
        if self.max_weight_kg is not None and self.max_weight_kg < 0:
            raise ValidationError("max_weight_kg must be non-negative")

    @property
    def identity(self) -> int:
        return self.id

    @property
    def full_address(self) -> str:
        parts = [p for p in (self.aisle, self.bay, self.level, self.bin) if p]
        return "-".join(parts) if parts else self.code


@dataclass(frozen=True)
class PositionInventoryItem:
    warehouse_id: int
    position_code: str
    product_id: int
    quantity: int

