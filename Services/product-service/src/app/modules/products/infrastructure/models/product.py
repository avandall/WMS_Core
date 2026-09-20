from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    Float,
    Index,
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

    uoms = relationship(
        "ProductUomModel",
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="joined",
    )

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
