from sqlalchemy import BigInteger, Column, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.shared.core.database import Base


class DocumentItemModel(Base):
    __tablename__ = "document_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.document_id"), nullable=False)
    product_id = Column(BigInteger, nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)

    # Phase 6: Document line lifecycle fields
    requested_qty = Column(Integer, nullable=True)
    reserved_qty = Column(Integer, nullable=True, default=0)
    executed_qty = Column(Integer, nullable=True)
    rejected_qty = Column(Integer, nullable=True, default=0)
    difference_qty = Column(Integer, nullable=True, default=0)
    execution_status = Column(String(50), nullable=True)

    document = relationship("DocumentModel", back_populates="items")
