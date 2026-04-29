from datetime import datetime

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

    __table_args__ = (
        CheckConstraint('price >= 0', name='check_product_price_positive'),
        Index('ix_products_name', 'name'),
    )

    inventory = relationship(
        "InventoryModel",
        back_populates="product",
        uselist=False,
        cascade="all, delete-orphan",
    )
    warehouse_items = relationship("WarehouseInventoryModel", back_populates="product")
    document_items = relationship("DocumentItemModel", back_populates="product")
