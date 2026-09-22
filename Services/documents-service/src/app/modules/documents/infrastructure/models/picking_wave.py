from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Integer, String, JSON
from app.shared.core.database import Base


class PickingWaveModel(Base):
    """SQLAlchemy model for persisting Wave Picking batches."""

    __tablename__ = "picking_waves"

    wave_id = Column(String(100), primary_key=True)
    carrier = Column(String(100), nullable=False, index=True)
    dispatch_cutoff = Column(DateTime(timezone=True), nullable=False)
    max_orders = Column(Integer, nullable=False, default=50)
    status = Column(String(50), nullable=False, default="DRAFT", index=True)
    orders = Column(JSON, nullable=False, default=list)
    picking_tasks = Column(JSON, nullable=False, default=list)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
