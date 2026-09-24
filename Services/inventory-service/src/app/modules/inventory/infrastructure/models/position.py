from sqlalchemy import Column, Float, Integer, String
from app.shared.core.database import Base


class InventoryPositionModel(Base):
    __tablename__ = "positions"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    warehouse_id = Column(Integer, nullable=False)
    code = Column(String(50), nullable=False)
    type = Column(String(20), nullable=False, default="STORAGE")
    description = Column(String(255), nullable=True)
    capacity = Column(Integer, nullable=True)
    zone = Column(String(50), nullable=True)
    is_active = Column(Integer, nullable=False, default=1)

    # Physical address & dimensions (TASK-029 & TASK-055)
    aisle = Column(String(50), nullable=True)
    bay = Column(String(50), nullable=True)
    level = Column(String(50), nullable=True)
    bin = Column(String(50), nullable=True)
    max_weight_kg = Column(Float, nullable=True)
    temperature_zone = Column(String(50), nullable=False, default="ambient")
    pick_sequence = Column(Integer, nullable=False, default=0)
    hazmat_class = Column(String(50), nullable=True)

    # Spatial coordinates & volume (TASK-046 & TASK-055)
    x_coordinate = Column(Float, nullable=True, default=0.0)
    y_coordinate = Column(Float, nullable=True, default=0.0)
    z_coordinate = Column(Float, nullable=True, default=0.0)
    max_volume_cbm = Column(Float, nullable=True)
    available_volume = Column(Float, nullable=True)
    available_weight = Column(Float, nullable=True)


PositionModel = InventoryPositionModel
