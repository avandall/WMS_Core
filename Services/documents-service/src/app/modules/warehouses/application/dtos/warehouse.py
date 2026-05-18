from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.modules.inventory.application.dtos.inventory import InventoryItemResponse


class WarehouseCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=20)
    address: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(None, max_length=500)


class WarehouseUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    address: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(None, max_length=500)


class WarehouseResponse(BaseModel):
    warehouse_id: int
    name: str
    code: str
    address: Optional[str]
    description: Optional[str]
    created_at: datetime
    total_products: int = 0
    total_stock_value: float = 0.0


class WarehouseDetailResponse(WarehouseResponse):
    inventory_items: List[InventoryItemResponse] = []


class WarehouseSearchRequest(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    has_products: Optional[bool] = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


class WarehouseListResponse(BaseModel):
    warehouses: List[WarehouseResponse]
    total: int
    page: int
    page_size: int


class WarehouseStats(BaseModel):
    warehouse_id: int
    warehouse_name: str
    total_products: int
    total_quantity: int
    low_stock_products: int
    total_value: float
