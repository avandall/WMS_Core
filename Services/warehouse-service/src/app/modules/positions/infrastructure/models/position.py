from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
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
    capacity = Column(Integer)
    zone = Column(String(50))
    is_active = Column(Integer, nullable=False, default=1, index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)

    # Physical WMS address & attributes (TASK-029)
    aisle = Column(String(50), nullable=True)
    bay = Column(String(50), nullable=True)
    level = Column(String(50), nullable=True)
    bin = Column(String(50), nullable=True)
    max_weight_kg = Column(Float, nullable=True)
    temperature_zone = Column(String(50), nullable=False, default="ambient")
    pick_sequence = Column(Integer, nullable=False, default=0, index=True)
    hazmat_class = Column(String(50), nullable=True)

    __table_args__ = (
        UniqueConstraint("warehouse_id", "code", name="uq_position_warehouse_code"),
        Index("ix_positions_warehouse_code", "warehouse_id", "code"),
        Index("ix_positions_warehouse_type", "warehouse_id", "type"),
    )

    warehouse = relationship("WarehouseModel", back_populates="positions")

