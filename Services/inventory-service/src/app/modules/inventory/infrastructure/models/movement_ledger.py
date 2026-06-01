from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.shared.core.database import Base


class InventoryMovementLedgerModel(Base):
    __tablename__ = "inventory_movement_ledger"

    event_id = Column(String(200), primary_key=True)
    movement_type = Column(String(50), nullable=False)
    document_id = Column(Integer, nullable=True, index=True)
    payload_json = Column(Text, nullable=False)
    applied_at = Column(DateTime, default=datetime.now, nullable=False)
