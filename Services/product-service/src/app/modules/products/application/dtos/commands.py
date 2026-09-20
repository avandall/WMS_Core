from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional


@dataclass(frozen=True)
class CreateProduct:
    product_id: int | None = None
    name: str | None = None
    price: float | None = None
    description: str | None = None
    length_cm: float | None = 0.0
    width_cm: float | None = 0.0
    height_cm: float | None = 0.0
    gross_weight_kg: float | None = 0.0
    net_weight_kg: float | None = 0.0
    base_uom: str | None = "EACH"
    uoms: Optional[List[Any]] = None


@dataclass(frozen=True)
class UpdateProduct:
    product_id: int
    name: str | None = None
    price: float | None = None
    description: str | None = None
    length_cm: float | None = None
    width_cm: float | None = None
    height_cm: float | None = None
    gross_weight_kg: float | None = None
    net_weight_kg: float | None = None
    base_uom: str | None = None
    uoms: Optional[List[Any]] = None
