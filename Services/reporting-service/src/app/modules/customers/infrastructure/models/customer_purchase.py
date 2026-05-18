from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer
from sqlalchemy.orm import relationship

from app.shared.core.database import Base


class CustomerPurchaseModel(Base):
    __tablename__ = "customer_purchases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.customer_id"), nullable=False, index=True)
    document_id = Column(Integer, ForeignKey("documents.document_id"), nullable=False, index=True)
    total_value = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)

    customer = relationship("CustomerModel", back_populates="purchases")
