from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


class CustomerCreate(BaseModel):
    name: str = Field(..., min_length=1)
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None


class CustomerResponse(BaseModel):
    customer_id: int
    name: str
    email: Optional[EmailStr]
    phone: Optional[str]
    address: Optional[str]
    debt_balance: float
    created_at: datetime
    purchase_count: int = 0
    total_purchased: float = 0.0


class DebtUpdate(BaseModel):
    amount: float = Field(
        ..., description="Positive to increase debt, negative to reduce (payment)"
    )


class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None


class PurchaseResponse(BaseModel):
    document_id: int
    total_value: float
    created_at: datetime


class CustomerDetailResponse(CustomerResponse):
    purchases: List[PurchaseResponse] = []

