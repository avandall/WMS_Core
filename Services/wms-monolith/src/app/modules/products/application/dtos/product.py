"""Pydantic models for product/warehouse/document workflows.

This file mirrors `src-old/app/api/schemas/product.py` for compatibility.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import AliasChoices, BaseModel, Field, model_validator


class ProductCreate(BaseModel):
    product_id: Optional[int] = Field(
        None, gt=0, description="Optional explicit product ID (legacy compatibility)"
    )
    name: str = Field(..., min_length=1, max_length=100, description="Product name")
    price: float = Field(
        0.0,
        ge=0,
        description="Optional catalog/list price (defaults to 0). Transaction pricing is defined per document item unit_price.",
    )
    description: Optional[str] = Field(
        None, max_length=500, description="Product description"
    )


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    price: Optional[float] = Field(
        None,
        ge=0,
        description="Catalog/list price. Transaction pricing is defined per document item unit_price.",
    )
    description: Optional[str] = Field(None, max_length=500)


class ProductResponse(BaseModel):
    product_id: int
    name: str
    price: float
    description: Optional[str]

    @classmethod
    def from_domain(cls, product):
        return cls(
            product_id=product.product_id,
            name=product.name,
            price=product.price,
            description=product.description,
        )


class InventoryItemResponse(BaseModel):
    product_id: int
    quantity: int

    @classmethod
    def from_domain(cls, item):
        return cls(product_id=item.product_id, quantity=item.quantity)


class WarehouseCreate(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Warehouse name",
        validation_alias=AliasChoices("name", "location"),
    )


class WarehouseResponse(BaseModel):
    warehouse_id: int
    name: str
    location: Optional[str] = None
    inventory: List[InventoryItemResponse]

    @classmethod
    def from_domain(cls, warehouse):
        return cls(
            warehouse_id=warehouse.warehouse_id,
            name=warehouse.location,
            location=warehouse.location,
            inventory=[InventoryItemResponse.from_domain(item) for item in warehouse.inventory],
        )


class WarehouseInventoryRowResponse(BaseModel):
    product_id: int
    warehouse_id: int
    warehouse_name: str
    quantity: int


class ProductMovement(BaseModel):
    product_id: int = Field(..., gt=0, description="Product identifier")
    quantity: int = Field(..., gt=0, description="Quantity to move")


class TransferInventoryRequest(BaseModel):
    to_warehouse_id: int = Field(..., gt=0, description="Destination warehouse ID")


class WarehouseTransferResponse(BaseModel):
    from_warehouse_id: int
    to_warehouse_id: int
    transferred_items: List[InventoryItemResponse]
    message: str


class DocumentProductItem(BaseModel):
    product_id: int = Field(..., gt=0)
    quantity: int = Field(..., gt=0)
    unit_price: Optional[float] = Field(
        None, ge=0, description="Optional; defaults to 0 for transfer/export/sale"
    )


class DocumentCreate(BaseModel):
    doc_type: Optional[str] = Field(None, description="Document type: import, export, or transfer")
    warehouse_id: Optional[int] = Field(None, gt=0, description="Legacy warehouse ID field for import/export requests")
    to_warehouse_id: Optional[int] = Field(None, gt=0, description="Legacy alias for destination warehouse ID")
    from_warehouse_id: Optional[int] = Field(None, gt=0, description="Legacy alias for source warehouse ID")
    destination_warehouse_id: Optional[int] = Field(None, gt=0, description="Target warehouse for import")
    source_warehouse_id: Optional[int] = Field(None, gt=0, description="Source warehouse for export or transfer")
    customer_id: Optional[int] = Field(None, gt=0, description="Customer ID for sale documents")
    items: List[DocumentProductItem] = Field(..., min_length=1, description="Document items")
    created_by: Optional[str] = Field(None, description="Creator name (auto-filled if not provided)")
    note: Optional[str] = Field(None, description="Optional note")

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_fields(cls, data):
        if not isinstance(data, dict):
            return data

        if data.get("destination_warehouse_id") is None:
            if data.get("to_warehouse_id") is not None:
                data["destination_warehouse_id"] = data["to_warehouse_id"]
            elif data.get("warehouse_id") is not None:
                data["destination_warehouse_id"] = data["warehouse_id"]

        if data.get("source_warehouse_id") is None:
            if data.get("from_warehouse_id") is not None:
                data["source_warehouse_id"] = data["from_warehouse_id"]
            elif data.get("warehouse_id") is not None:
                data["source_warehouse_id"] = data["warehouse_id"]

        return data


class DocumentPost(BaseModel):
    approved_by: str = Field(..., min_length=1, description="Approver name")


class DocumentResponse(BaseModel):
    document_id: int
    doc_type: str
    status: str
    from_warehouse_id: Optional[int]
    to_warehouse_id: Optional[int]
    customer_id: Optional[int]
    items: List[DocumentProductItem]
    created_by: str
    approved_by: Optional[str]
    date: datetime
    note: Optional[str]

    @classmethod
    def from_domain(cls, document):
        return cls(
            document_id=document.document_id,
            doc_type=document.doc_type.value,
            status=document.status.value,
            from_warehouse_id=document.from_warehouse_id,
            to_warehouse_id=document.to_warehouse_id,
            items=[
                DocumentProductItem(
                    product_id=item.product_id,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                )
                for item in document.items
            ],
            created_by=document.created_by,
            approved_by=document.approved_by,
            date=document.date,
            note=document.note,
            customer_id=getattr(document, "customer_id", None),
        )


class InventoryReportItem(BaseModel):
    product_id: int
    quantity: int
    product_name: Optional[str]
    unit_value: Optional[float]


class WarehouseInventoryReport(BaseModel):
    warehouse_id: int
    warehouse_location: str
    items: List[InventoryReportItem]
    low_stock_items: List[InventoryReportItem]
    generated_at: datetime


class TotalInventoryReport(BaseModel):
    product_totals: List[InventoryReportItem]
    generated_at: datetime


class InventoryReportResponse(BaseModel):
    @classmethod
    def from_domain(cls, report):
        if hasattr(report, "warehouse_id"):
            return {
                "type": "warehouse_inventory",
                "warehouse_id": report.warehouse_id,
                "warehouse_location": report.warehouse_location,
                "items": [
                    {
                        "product_id": item.product_id,
                        "quantity": item.quantity,
                        "product_name": item.product_name,
                        "unit_value": item.unit_value,
                    }
                    for item in report.items
                ],
                "low_stock_items": [
                    {
                        "product_id": item.product_id,
                        "quantity": item.quantity,
                        "product_name": item.product_name,
                        "unit_value": item.unit_value,
                    }
                    for item in report.low_stock_items
                ],
                "generated_at": report.generated_at,
            }

        return {
            "type": "total_inventory",
            "product_totals": [
                {
                    "product_id": item.product_id,
                    "quantity": item.quantity,
                    "product_name": item.product_name,
                    "unit_value": item.unit_value,
                }
                for item in report.product_totals
            ],
            "generated_at": report.generated_at,
        }
