from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String
from sqlalchemy.orm import relationship

from app.shared.core.database import Base


class CustomerModel(Base):
    __tablename__ = "customers"

    customer_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False, index=True)
    email = Column(String(255))
    phone = Column(String(50))
    address = Column(String(255))
    debt_balance = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)

    purchases = relationship("CustomerPurchaseModel", back_populates="customer")
