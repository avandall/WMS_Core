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


@dataclass(frozen=True)
class PositionType:
    value: str

    ALLOWED = {"RECEIVING", "STORAGE", "SHIPPING", "SYSTEM", "PICKING", "RETURN"}

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not self.value.strip():
            raise ValidationError("position type is required")
        normalized = self.value.strip().upper()
        if normalized not in self.ALLOWED:
            raise ValidationError(f"position type must be one of {sorted(self.ALLOWED)}")
        object.__setattr__(self, "value", normalized)
