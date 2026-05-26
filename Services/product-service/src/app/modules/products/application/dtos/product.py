"""Pydantic models for product catalog workflows."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


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
