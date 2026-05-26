from sqlalchemy import BigInteger, CheckConstraint, Column, Integer

from app.shared.core.database import Base


class InventoryModel(Base):
    __tablename__ = "inventory"

    product_id = Column(BigInteger, primary_key=True)
    quantity = Column(Integer, nullable=False, default=0)

    __table_args__ = (
        CheckConstraint('quantity >= 0', name='check_inventory_quantity_positive'),
    )
