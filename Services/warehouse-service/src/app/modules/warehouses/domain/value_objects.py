from __future__ import annotations

from dataclasses import dataclass

from app.shared.domain.business_exceptions import ValidationError


@dataclass(frozen=True)
class WarehouseLocation:
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not self.value.strip():
            raise ValidationError("location must be a non-empty string")
        normalized = " ".join(self.value.strip().split())
        if len(normalized) > 200:
            raise ValidationError("location must be at most 200 characters")
        object.__setattr__(self, "value", normalized)


@dataclass(frozen=True)
class BinCode:
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not self.value.strip():
            raise ValidationError("position code is required")
        normalized = self.value.strip().upper()
        if len(normalized) > 50:
            raise ValidationError("position code must be at most 50 characters")
        object.__setattr__(self, "value", normalized)


from typing import ClassVar


@dataclass(frozen=True)
class PositionType:
    value: str

    ALLOWED: ClassVar[set[str]] = {"RECEIVING", "STORAGE", "SHIPPING", "SYSTEM", "PICKING", "RETURN"}

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not self.value.strip():
            raise ValidationError("position type is required")
        normalized = self.value.strip().upper()
        if normalized not in self.ALLOWED:
            raise ValidationError(f"position type must be one of {sorted(self.ALLOWED)}")
        object.__setattr__(self, "value", normalized)


@dataclass(frozen=True)
class WarehouseType:
    value: str

    ALLOWED: ClassVar[set[str]] = {"ambient", "cold", "frozen", "hazmat"}

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not self.value.strip():
            raise ValidationError("warehouse_type must be a non-empty string")
        normalized = self.value.strip().lower()
        if normalized not in self.ALLOWED:
            raise ValidationError(f"warehouse_type must be one of {sorted(self.ALLOWED)}")
        object.__setattr__(self, "value", normalized)


@dataclass(frozen=True)
class TemperatureZone:
    value: str

    ALLOWED: ClassVar[set[str]] = {"ambient", "chilled", "frozen"}

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not self.value.strip():
            raise ValidationError("temperature_zone must be a non-empty string")
        normalized = self.value.strip().lower()
        if normalized not in self.ALLOWED:
            raise ValidationError(f"temperature_zone must be one of {sorted(self.ALLOWED)}")
        object.__setattr__(self, "value", normalized)


