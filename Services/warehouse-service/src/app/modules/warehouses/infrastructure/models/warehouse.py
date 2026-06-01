from sqlalchemy import (
    Column,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

from app.shared.core.database import Base


class WarehouseModel(Base):
    __tablename__ = "warehouses"

    warehouse_id = Column(Integer, primary_key=True, autoincrement=True)
    location = Column(String(200), nullable=False, unique=True, index=True)

    positions = relationship(
        "PositionModel",
        back_populates="warehouse",
        cascade="all, delete-orphan",
    )
