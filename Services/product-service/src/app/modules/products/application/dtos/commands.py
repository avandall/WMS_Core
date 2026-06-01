from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CreateProduct:
    product_id: int | None = None
    name: str | None = None
    price: float | None = None
    description: str | None = None


@dataclass(frozen=True)
class UpdateProduct:
    product_id: int
    name: str | None = None
    price: float | None = None
    description: str | None = None
