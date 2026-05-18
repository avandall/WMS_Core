from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class InventoryItemCreate(BaseModel):
    product_id: int = Field(..., gt=0)
    warehouse_id: int = Field(..., gt=0)
    quantity: int = Field(..., ge=0)


class InventoryItemUpdate(BaseModel):
    quantity: int = Field(..., ge=0)


class InventoryItemResponse(BaseModel):
    product_id: int
    product_name: str
    warehouse_id: int
    warehouse_name: str
    quantity: int
    last_updated: datetime


class InventoryAdjustment(BaseModel):
    product_id: int = Field(..., gt=0)
    warehouse_id: int = Field(..., gt=0)
    quantity_change: int = Field(..., description="Positive to add, negative to remove")
    reason: Optional[str] = None


class StockMovementRequest(BaseModel):
    product_id: int = Field(..., gt=0)
    from_warehouse_id: Optional[int] = Field(None, gt=0)
    to_warehouse_id: Optional[int] = Field(None, gt=0)
    quantity: int = Field(..., gt=0)
    reason: Optional[str] = None


class InventorySearchRequest(BaseModel):
    warehouse_id: Optional[int] = None
    product_id: Optional[int] = None
    low_stock_threshold: Optional[int] = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


class InventoryListResponse(BaseModel):
    items: List[InventoryItemResponse]
    total: int
    page: int
    page_size: int


class LowStockItem(BaseModel):
    product_id: int
    product_name: str
    warehouse_id: int
    warehouse_name: str
    current_quantity: int
    min_quantity: int
