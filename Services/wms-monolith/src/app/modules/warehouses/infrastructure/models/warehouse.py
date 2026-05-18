from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship

from app.shared.core.database import Base


class WarehouseModel(Base):
    __tablename__ = "warehouses"

    warehouse_id = Column(Integer, primary_key=True, autoincrement=True)
    location = Column(String(200), nullable=False, unique=True, index=True)

    inventory_items = relationship(
        "WarehouseInventoryModel",
        back_populates="warehouse",
        cascade="all, delete-orphan",
    )
    positions = relationship(
        "PositionModel",
        back_populates="warehouse",
        cascade="all, delete-orphan",
    )


class WarehouseInventoryModel(Base):
    __tablename__ = "warehouse_inventory"

    id = Column(Integer, primary_key=True, autoincrement=True)
    warehouse_id = Column(
        Integer, ForeignKey("warehouses.warehouse_id"), nullable=False, index=True
    )
    product_id = Column(BigInteger, ForeignKey("products.product_id"), nullable=False, index=True)
    quantity = Column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("warehouse_id", "product_id", name="uq_warehouse_product"),
        CheckConstraint('quantity >= 0', name='check_warehouse_inventory_quantity_positive'),
        Index('ix_warehouse_inventory_warehouse_product', 'warehouse_id', 'product_id'),
    )

    warehouse = relationship("WarehouseModel", back_populates="inventory_items")
    product = relationship("ProductModel", back_populates="warehouse_items")
