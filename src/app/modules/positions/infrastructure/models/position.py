from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship

from app.shared.core.database import Base


class PositionModel(Base):
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    warehouse_id = Column(
        Integer, ForeignKey("warehouses.warehouse_id"), nullable=False, index=True
    )
    code = Column(String(50), nullable=False)
    type = Column(String(20), nullable=False, default="STORAGE", index=True)
    description = Column(String(255))
    is_active = Column(Integer, nullable=False, default=1, index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("warehouse_id", "code", name="uq_position_warehouse_code"),
        Index("ix_positions_warehouse_code", "warehouse_id", "code"),
        Index("ix_positions_warehouse_type", "warehouse_id", "type"),
    )

    warehouse = relationship("WarehouseModel", back_populates="positions")
    inventory_items = relationship(
        "PositionInventoryModel",
        back_populates="position",
        cascade="all, delete-orphan",
    )
