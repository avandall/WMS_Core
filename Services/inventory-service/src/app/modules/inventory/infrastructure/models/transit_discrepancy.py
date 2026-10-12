from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String
from app.shared.core.database import Base


class TransitDiscrepancyModel(Base):
    """
    TASK-098 / DOM-08: Tracks short-shipments, transit damages, and shrinkage
    during inter-warehouse transfer reconciliation.
    """
    __tablename__ = "transit_discrepancy_records"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, nullable=False, index=True)
    product_id = Column(Integer, nullable=False, index=True)
    from_warehouse_id = Column(Integer, nullable=False)
    to_warehouse_id = Column(Integer, nullable=False)
    shipped_quantity = Column(Integer, nullable=False, default=0)
    received_quantity = Column(Integer, nullable=False, default=0)
    discrepancy_quantity = Column(Integer, nullable=False, default=0)
    discrepancy_type = Column(String(50), nullable=False, default="SHORT_SHIPMENT")  # SHORT_SHIPMENT, DAMAGED, LOST
    owner_id = Column(String(100), nullable=False, default="DEFAULT_OWNER")
    status = Column(String(50), nullable=False, default="LOGGED")  # LOGGED, WRITTEN_OFF, RECONCILED
    note = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
