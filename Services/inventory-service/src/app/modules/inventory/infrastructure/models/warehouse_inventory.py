from sqlalchemy import BigInteger, CheckConstraint, Column, Integer, Index, UniqueConstraint

from app.shared.core.database import Base


class WarehouseInventoryModel(Base):
    __tablename__ = "warehouse_inventory"

    id = Column(Integer, primary_key=True, autoincrement=True)
    warehouse_id = Column(Integer, nullable=False, index=True)
    product_id = Column(BigInteger, nullable=False, index=True)
    quantity = Column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("warehouse_id", "product_id", name="uq_warehouse_product"),
        CheckConstraint("quantity >= 0", name="check_warehouse_inventory_quantity_positive"),
        Index("ix_warehouse_inventory_warehouse_product", "warehouse_id", "product_id"),
    )
