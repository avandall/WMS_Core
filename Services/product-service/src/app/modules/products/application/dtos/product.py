"""Pydantic models for product catalog workflows."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ProductUomDTO(BaseModel):
    uom_code: str = Field(..., min_length=1, max_length=20, description="UOM code, e.g. CARTON, PALLET")
    conversion_factor: float = Field(1.0, gt=0, description="Conversion ratio relative to target unit")
    to_uom_code: str = Field("EACH", min_length=1, max_length=20, description="Target unit code, e.g. EACH, CARTON")


class ProductCreate(BaseModel):
    product_id: Optional[int] = Field(
        None, gt=0, description="Optional explicit product ID (legacy compatibility)"
    )
    name: str = Field(..., min_length=1, max_length=100, description="Product name")
    price: float = Field(
        0.0,
        ge=0,
        description="Optional catalog/list price (defaults to 0).",
    )
    description: Optional[str] = Field(
        None, max_length=500, description="Product description"
    )
    length_cm: float = Field(0.0, ge=0, description="Length in cm")
    width_cm: float = Field(0.0, ge=0, description="Width in cm")
    height_cm: float = Field(0.0, ge=0, description="Height in cm")
    gross_weight_kg: float = Field(0.0, ge=0, description="Gross weight in kg")
    net_weight_kg: float = Field(0.0, ge=0, description="Net weight in kg")
    base_uom: str = Field("EACH", min_length=1, max_length=20, description="Base unit of measure")
    uoms: List[ProductUomDTO] = Field(default_factory=list, description="UOM conversion definitions")


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    price: Optional[float] = Field(None, ge=0)
    description: Optional[str] = Field(None, max_length=500)
    length_cm: Optional[float] = Field(None, ge=0)
    width_cm: Optional[float] = Field(None, ge=0)
    height_cm: Optional[float] = Field(None, ge=0)
    gross_weight_kg: Optional[float] = Field(None, ge=0)
    net_weight_kg: Optional[float] = Field(None, ge=0)
    base_uom: Optional[str] = Field(None, min_length=1, max_length=20)
    uoms: Optional[List[ProductUomDTO]] = None


class ProductResponse(BaseModel):
    product_id: int
    name: str
    price: float
    description: Optional[str] = None
    length_cm: float = 0.0
    width_cm: float = 0.0
    height_cm: float = 0.0
    gross_weight_kg: float = 0.0
    net_weight_kg: float = 0.0
    volume_cbm: float = 0.0
    base_uom: str = "EACH"
    uoms: List[ProductUomDTO] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, product) -> ProductResponse:
        uom_dtos = [
            ProductUomDTO(
                uom_code=u.uom_code,
                conversion_factor=u.conversion_factor,
                to_uom_code=u.to_uom_code,
            )
            for u in getattr(product, "uoms", [])
        ]
        return cls(
            product_id=product.product_id,
            name=product.name,
            price=product.price,
            description=product.description,
            length_cm=getattr(product, "length_cm", 0.0),
            width_cm=getattr(product, "width_cm", 0.0),
            height_cm=getattr(product, "height_cm", 0.0),
            gross_weight_kg=getattr(product, "gross_weight_kg", 0.0),
            net_weight_kg=getattr(product, "net_weight_kg", 0.0),
            volume_cbm=getattr(product, "volume_cbm", 0.0),
            base_uom=getattr(product, "base_uom", "EACH"),
            uoms=uom_dtos,
        )
