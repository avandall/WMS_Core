from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Float,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

from app.shared.core.database import Base


class ProductModel(Base):
    __tablename__ = "products"

    product_id = Column(BigInteger, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(String(500))
    price = Column(Float, nullable=False, default=0.0)

    # Physical dimensions & weight (TASK-004)
    length_cm = Column(Float, nullable=False, default=0.0)
    width_cm = Column(Float, nullable=False, default=0.0)
    height_cm = Column(Float, nullable=False, default=0.0)
    gross_weight_kg = Column(Float, nullable=False, default=0.0)
    net_weight_kg = Column(Float, nullable=False, default=0.0)
    base_uom = Column(String(20), nullable=False, default="EACH")

    # 3D Packing & Hazmat attributes (TASK-045)
    allow_rotation = Column(Boolean, nullable=False, default=True)
    hazmat_class = Column(String(50), nullable=True)
    category = Column(String(50), nullable=True)

    # Palletizing parameters (Ti x Hi) & Multi-UOM (TASK-052)
    ti = Column(Integer, nullable=False, default=0)  # Number of cartons per tier / layer
    hi = Column(Integer, nullable=False, default=0)  # Number of tiers / layers per pallet
    tie_high = Column(String(20), nullable=True)     # Pallet configuration string e.g. "10x5"

    uoms = relationship(
        "ProductUomModel",
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="joined",
    )

    @property
    def ti_hi(self) -> str:
        if self.ti and self.hi:
            return f"{self.ti}x{self.hi}"
        return self.tie_high or ""

    @property
    def product_uom_conversions(self) -> list:
        """Alias for multi-tier UOM conversions."""
        return self.uoms

    def convert_uom_quantity(self, quantity: float, from_uom: str, to_uom: str = "EACH") -> float:
        """Converts quantity between UOM tiers (e.g. PALLET -> CASE -> EACH)."""
        if from_uom.upper() == to_uom.upper():
            return float(quantity)
        uom_map = {u.uom_code.upper(): float(u.conversion_factor) for u in (self.uoms or [])}
        uom_map[self.base_uom.upper()] = 1.0
        if from_uom.upper() not in uom_map:
            raise ValueError(f"Unknown source UOM: {from_uom}")
        if to_uom.upper() not in uom_map:
            raise ValueError(f"Unknown target UOM: {to_uom}")
        
        # Convert source quantity to base unit (EACH), then convert to target unit
        qty_in_base = float(quantity) * uom_map[from_uom.upper()]
        return qty_in_base / uom_map[to_uom.upper()]

    @property
    def volume_cbm(self) -> float:
        if self.length_cm and self.width_cm and self.height_cm:
            return float((self.length_cm * self.width_cm * self.height_cm) / 1_000_000.0)
        return 0.0

    __table_args__ = (
        CheckConstraint("price >= 0", name="check_product_price_positive"),
        CheckConstraint("length_cm >= 0", name="check_product_length_positive"),
        CheckConstraint("width_cm >= 0", name="check_product_width_positive"),
        CheckConstraint("height_cm >= 0", name="check_product_height_positive"),
        CheckConstraint("gross_weight_kg >= 0", name="check_product_gross_weight_positive"),
        CheckConstraint("net_weight_kg >= 0", name="check_product_net_weight_positive"),
        Index("ix_products_name", "name"),
    )
