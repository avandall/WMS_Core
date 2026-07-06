from __future__ import annotations

from pydantic import BaseModel, Field


class CustomerPayload(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    address: str = ""


class CustomerDebtPayload(BaseModel):
    amount: float = 0


class ProductPayload(BaseModel):
    product_id: int = 0
    name: str = ""
    price: float = 0
    description: str = ""


class WarehousePayload(BaseModel):
    name: str = ""


class WarehouseTransferPayload(BaseModel):
    to_warehouse_id: int = 0


class DocumentItemPayload(BaseModel):
    product_id: int = 0
    quantity: int = 0
    unit_price: float = 0


class DocumentPayload(BaseModel):
    source_warehouse_id: int = 0
    destination_warehouse_id: int = 0
    warehouse_id: int = 0
    customer_id: int = 0
    items: list[DocumentItemPayload] = Field(default_factory=list)
    created_by: str = "system"
    note: str = ""
    transaction_type: str = ""
    reason_code: str = ""


class PostDocumentPayload(BaseModel):
    approved_by: str = ""


class AIQueryPayload(BaseModel):
    question: str = ""
    mode: str = "auto"


class ConfirmItemPayload(BaseModel):
    product_id: int = 0
    quantity: int = 0


class ConfirmExecutionPayload(BaseModel):
    items: list[ConfirmItemPayload] = Field(default_factory=list)


class LoginPayload(BaseModel):
    email: str = ""
    password: str = ""


