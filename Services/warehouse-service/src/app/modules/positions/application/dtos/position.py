from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class PositionCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    type: str = Field("STORAGE", min_length=1, max_length=20)
    description: Optional[str] = Field(None, max_length=255)


class PositionResponse(BaseModel):
    id: int
    warehouse_id: int
    code: str
    type: str
    description: Optional[str] = None
    is_active: bool
