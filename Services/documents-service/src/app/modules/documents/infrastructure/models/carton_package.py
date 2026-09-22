from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Float, String, JSON
from app.shared.core.database import Base


class CartonPackageModel(Base):
    """SQLAlchemy model for persisting Pack Station cartons and weight verification results."""

    __tablename__ = "carton_packages"

    carton_id = Column(String(100), primary_key=True)
    order_id = Column(String(100), nullable=False, index=True)
    packaging_tare_weight_g = Column(Float, nullable=False, default=100.0)
    status = Column(String(50), nullable=False, default="PACKING", index=True)
    measured_weight_g = Column(Float, nullable=True)
    verification_result = Column(JSON, nullable=True)
    items = Column(JSON, nullable=False, default=list)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
