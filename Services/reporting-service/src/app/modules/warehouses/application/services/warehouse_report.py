"""Warehouse report dataclasses."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass
class WarehousePerformanceItem:
    warehouse_id: int
    location: str
    item_count: int
    total_quantity: int
    total_value: Optional[float]


@dataclass
class WarehousePerformanceReport:
    warehouses: List[WarehousePerformanceItem]
    generated_at: datetime

    @property
    def total_warehouses(self) -> int:
        return len(self.warehouses)

    @property
    def total_value(self) -> Optional[float]:
        values = [w.total_value for w in self.warehouses if w.total_value is not None]
        return sum(values) if values else None

