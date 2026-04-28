from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

from app.shared.core.database import Base


class DocumentModel(Base):
    __tablename__ = "documents"

    document_id = Column(Integer, primary_key=True, autoincrement=True)
    doc_type = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False)
    from_warehouse_id = Column(
        Integer, ForeignKey("warehouses.warehouse_id"), nullable=True, index=True
    )
    to_warehouse_id = Column(
        Integer, ForeignKey("warehouses.warehouse_id"), nullable=True, index=True
    )
    created_by = Column(String(100), nullable=False)
    approved_by = Column(String(100))
    note = Column(String(500))
    customer_id = Column(Integer, ForeignKey("customers.customer_id"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    posted_at = Column(DateTime, index=True)
    cancelled_at = Column(DateTime)
    cancellation_reason = Column(String(500))

    __table_args__ = (
        Index('ix_documents_status_created_at', 'status', 'created_at'),
        Index('ix_documents_type_status', 'doc_type', 'status'),
        Index('ix_documents_created_by_created_at', 'created_by', 'created_at'),
    )

    items = relationship(
        "DocumentItemModel",
        back_populates="document",
        cascade="all, delete-orphan",
    )
