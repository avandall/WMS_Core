"""Inventory report dataclasses."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass
class InventoryReportItem:
    product_id: int
    quantity: int
    product_name: Optional[str] = None
    unit_value: Optional[float] = None

    @property
    def total_value(self) -> Optional[float]:
        if self.unit_value is not None:
            return self.quantity * self.unit_value
        return None


@dataclass
class WarehouseInventoryReport:
    warehouse_id: int
    warehouse_location: str
    items: List[InventoryReportItem]
    low_stock_items: List[InventoryReportItem]
    generated_at: datetime

    @property
    def total_items(self) -> int:
        return len(self.items)

    @property
    def total_quantity(self) -> int:
        return sum(item.quantity for item in self.items)

    @property
    def total_value(self) -> Optional[float]:
        values = [item.total_value for item in self.items if item.total_value is not None]
        return sum(values) if values else None


@dataclass
class TotalInventoryReport:
    product_totals: List[InventoryReportItem]
    low_stock_items: List[InventoryReportItem]
    generated_at: datetime

    @property
    def total_products(self) -> int:
        return len(self.product_totals)

    @property
    def total_quantity(self) -> int:
        return sum(item.quantity for item in self.product_totals)

    @property
    def total_value(self) -> Optional[float]:
        values = [item.total_value for item in self.product_totals if item.total_value is not None]
        return sum(values) if values else None

