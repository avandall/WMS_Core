from sqlalchemy import BigInteger, Column

from app.shared.core.database import Base


class InventoryModel(Base):
    """Legacy Inventory model retained for table schema compatibility without stored total quantity column."""

    __tablename__ = "inventory"

    product_id = Column(BigInteger, primary_key=True)

