from datetime import datetime, timezone

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
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    # Physical WMS address & attributes (TASK-029)
    aisle = Column(String(50), nullable=True)
    bay = Column(String(50), nullable=True)
    level = Column(String(50), nullable=True)
    bin = Column(String(50), nullable=True)
    max_weight_kg = Column(Float, nullable=True)
    temperature_zone = Column(String(50), nullable=False, default="ambient")
    pick_sequence = Column(Integer, nullable=False, default=0, index=True)
    hazmat_class = Column(String(50), nullable=True)

    # Warehouse physical layout coordinates & capacity (TASK-046 & TASK-047)
    x_coordinate = Column(Float, nullable=True, default=0.0)
    y_coordinate = Column(Float, nullable=True, default=0.0)
    z_coordinate = Column(Float, nullable=True, default=0.0)
    max_volume_cbm = Column(Float, nullable=True)
    available_volume = Column(Float, nullable=True)
    available_weight = Column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint("warehouse_id", "code", name="uq_position_warehouse_code"),
        Index("ix_positions_warehouse_code", "warehouse_id", "code"),
        Index("ix_positions_warehouse_type", "warehouse_id", "type"),
        {"extend_existing": True},
    )

    warehouse = relationship("WarehouseModel", back_populates="positions")

