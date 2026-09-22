from sqlalchemy import (
    Boolean,
    Column,
    Float,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

from app.shared.core.database import Base


class WarehouseModel(Base):
    __tablename__ = "warehouses"

    warehouse_id = Column(Integer, primary_key=True, autoincrement=True)
    location = Column(String(200), nullable=False, unique=True, index=True)
    warehouse_type = Column(String(50), nullable=False, default="ambient")
    capacity_sqm = Column(Float, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    manager_id = Column(String(100), nullable=True)
    timezone = Column(String(50), nullable=False, default="UTC")


    positions = relationship(
        "PositionModel",
        back_populates="warehouse",
        cascade="all, delete-orphan",
    )

