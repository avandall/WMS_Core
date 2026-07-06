from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, Integer, String, UniqueConstraint

from app.shared.core.database import Base


class StockReservationModel(Base):
    __tablename__ = "stock_reservations"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    source_type = Column(String(50), nullable=False)  # e.g., "document", "manual", "order"
    source_id = Column(BigInteger, nullable=True)
    document_id = Column(BigInteger, nullable=True)
    product_id = Column(BigInteger, nullable=False, index=True)
    warehouse_id = Column(Integer, nullable=False, index=True)
    requested_qty = Column(Integer, nullable=False)
    reserved_qty = Column(Integer, nullable=False, default=0)
    released_qty = Column(Integer, nullable=False, default=0)
    consumed_qty = Column(Integer, nullable=False, default=0)
    status = Column(String(50), nullable=False, default="PENDING")  # PENDING, RESERVED, RELEASED, CONSUMED, EXPIRED
    expires_at = Column(DateTime, nullable=True)
    created_by = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Phase 4: Idempotency key to prevent duplicate reservations
    # NOTE: unique=True is intentionally NOT set here; the named constraint in
    # __table_args__ (uq_stock_reservation_idempotency) handles uniqueness so that
    # PostgreSQL does not create two separate UNIQUE indexes on the same column.
    idempotency_key = Column(String(255), nullable=True)

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_stock_reservation_idempotency"),
        UniqueConstraint("source_type", "source_id", name="uq_stock_reservation_source"),
    )
