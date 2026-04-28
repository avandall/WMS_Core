from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.shared.core.database import Base


class PositionInventoryModel(Base):
    __tablename__ = "position_inventory"

    id = Column(Integer, primary_key=True, autoincrement=True)
    position_id = Column(
        Integer, ForeignKey("positions.id"), nullable=False, index=True
    )
    product_id = Column(
        BigInteger, ForeignKey("products.product_id"), nullable=False, index=True
    )
    quantity = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime, default=datetime.now, nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("position_id", "product_id", name="uq_position_product"),
        CheckConstraint(
            "quantity >= 0", name="check_position_inventory_quantity_positive"
        ),
        Index("ix_position_inventory_position_product", "position_id", "product_id"),
    )

    position = relationship("PositionModel", back_populates="inventory_items")
    product = relationship("ProductModel")
