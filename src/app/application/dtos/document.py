from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.domain.entities.document import DocumentStatus, DocumentType


class DocumentItemCreate(BaseModel):
    product_id: int = Field(..., gt=0)
    quantity: int = Field(..., gt=0)
    unit_price: Optional[float] = Field(None, ge=0)


class DocumentItemResponse(BaseModel):
    product_id: int
    product_name: str
    quantity: int
    unit_price: Optional[float]
    total_value: float


class DocumentCreate(BaseModel):
    doc_type: DocumentType
    from_warehouse_id: Optional[int] = Field(None, gt=0)
    to_warehouse_id: Optional[int] = Field(None, gt=0)
    customer_id: Optional[int] = Field(None, gt=0)
    items: List[DocumentItemCreate] = Field(..., min_items=1)
    created_by: str = Field(..., min_length=1)
    note: Optional[str] = None


class DocumentResponse(BaseModel):
    document_id: int
    doc_type: DocumentType
    status: DocumentStatus
    from_warehouse_id: Optional[int]
    to_warehouse_id: Optional[int]
    customer_id: Optional[int]
    items: List[DocumentItemResponse]
    created_by: str
    created_at: datetime
    posted_at: Optional[datetime]
    note: Optional[str]
    total_value: float


class DocumentUpdate(BaseModel):
    note: Optional[str] = None


class DocumentStatusUpdate(BaseModel):
    status: DocumentStatus


class DocumentListResponse(BaseModel):
    documents: List[DocumentResponse]
    total: int
    page: int
    page_size: int


class DocumentSearchRequest(BaseModel):
    doc_type: Optional[DocumentType] = None
    status: Optional[DocumentStatus] = None
    warehouse_id: Optional[int] = None
    customer_id: Optional[int] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
