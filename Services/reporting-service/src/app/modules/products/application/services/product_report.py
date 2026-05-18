"""Product report dataclasses."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass
class ProductMovementItem:
    product_id: int
    product_name: str
    imported: int
    exported: int
    transferred_in: int
    transferred_out: int
    net_movement: int


@dataclass
class ProductMovementReport:
    items: List[ProductMovementItem]
    start_date: datetime
    end_date: datetime
    generated_at: datetime

    @property
    def total_products(self) -> int:
        return len(self.items)

    @property
    def total_imported(self) -> int:
        return sum(item.imported for item in self.items)

    @property
    def total_exported(self) -> int:
        return sum(item.exported for item in self.items)

