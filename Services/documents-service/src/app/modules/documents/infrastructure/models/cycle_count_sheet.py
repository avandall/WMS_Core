from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Float, Integer, String, JSON
from app.shared.core.database import Base


class CycleCountSheetModel(Base):
    """SQLAlchemy model for persisting Blind Cycle Counting sheets and approval status."""

    __tablename__ = "cycle_count_sheets"

    cycle_count_id = Column(String(100), primary_key=True)
    warehouse_id = Column(Integer, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    assigned_to = Column(String(100), nullable=True, index=True)
    status = Column(String(50), nullable=False, default="DRAFT", index=True)
    discrepancy_qty_threshold = Column(Integer, nullable=False, default=0)
    discrepancy_value_threshold = Column(Float, nullable=False, default=0.0)
    created_by = Column(String(100), nullable=False, default="system")
    note = Column(String(500), nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    approved_by = Column(String(100), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(String(500), nullable=True)
    items = Column(JSON, nullable=False, default=list)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
