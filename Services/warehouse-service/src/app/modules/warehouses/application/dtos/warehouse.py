from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class WarehouseCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


class WarehouseUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)


class WarehouseResponse(BaseModel):
    warehouse_id: int
    name: str
    location: Optional[str] = None

    @classmethod
    def from_domain(cls, warehouse):
        return cls(
            warehouse_id=warehouse.warehouse_id,
            name=warehouse.location,
            location=warehouse.location,
        )
