from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, Index, Integer, String, Text, UniqueConstraint

from app.shared.core.database import Base


class InventoryTransactionModel(Base):
    __tablename__ = "inventory_transactions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    transaction_type = Column(String(50), nullable=False)  # e.g., "ADJUSTMENT", "RESERVATION", "CONSUMPTION", "RECEIPT"
    document_id = Column(BigInteger, nullable=True, index=True)
    document_line_id = Column(BigInteger, nullable=True)
    product_id = Column(BigInteger, nullable=False, index=True)
    warehouse_id = Column(Integer, nullable=False, index=True)
    quantity = Column(Integer, nullable=False)
    physical_qty_before = Column(Integer, nullable=True)
    physical_qty_after = Column(Integer, nullable=True)
    reserved_qty_before = Column(Integer, nullable=True)
    reserved_qty_after = Column(Integer, nullable=True)
    available_qty_before = Column(Integer, nullable=True)
    available_qty_after = Column(Integer, nullable=True)
    user_id = Column(String(100), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    payload = Column(Text, nullable=True)
    
    # Phase 9: Idempotency key to prevent duplicate transactions
    idempotency_key = Column(String(255), nullable=True, unique=True)

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_inventory_transaction_idempotency"),
        Index('ix_inventory_transactions_document_product', 'document_id', 'product_id'),
        Index('ix_inventory_transactions_warehouse_product', 'warehouse_id', 'product_id'),
        Index('ix_inventory_transactions_created_at', 'created_at'),
    )
