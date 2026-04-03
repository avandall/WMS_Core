from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship

from app.core.database import Base


class AuditEventModel(Base):
    """Business-level audit events for warehouse operations."""

    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String(64), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True)
    entity_type = Column(String(100), nullable=True, index=True)
    entity_id = Column(String(100), nullable=True, index=True)
    warehouse_id = Column(Integer, ForeignKey("warehouses.warehouse_id"), nullable=True, index=True)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)

    user = relationship("UserModel")
    warehouse = relationship("WarehouseModel")

    __table_args__ = (
        Index("ix_audit_events_action_created", "action", "created_at"),
        Index("ix_audit_events_entity", "entity_type", "entity_id"),
    )

