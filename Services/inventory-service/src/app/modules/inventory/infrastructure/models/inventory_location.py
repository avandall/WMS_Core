from datetime import datetime, timezone
from sqlalchemy import BigInteger, Boolean, CheckConstraint, Column, DateTime, Index, Integer, String, UniqueConstraint

from app.shared.core.database import Base


class InventoryLocationModel(Base):
    __tablename__ = "inventory_locations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    warehouse_id = Column(Integer, nullable=False, index=True)
    owner_id = Column(String(100), nullable=False, default="DEFAULT_OWNER", index=True)
    position_id = Column(Integer, nullable=False, index=True)
    product_id = Column(BigInteger, nullable=False, index=True)
    lpn = Column(String(100), nullable=False, default="", index=True)
    lot_number = Column(String(100), nullable=False, default="", index=True)
    mfg_date = Column(DateTime(timezone=True), nullable=True)
    expiry_date = Column(DateTime(timezone=True), nullable=True, index=True)
    quantity = Column(Integer, nullable=False, default=0)
    allocated_qty = Column(Integer, nullable=False, default=0)
    status = Column(String(50), nullable=False, default="AVAILABLE", index=True)
    is_counting = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "warehouse_id", "owner_id", "position_id", "product_id", "lpn", "lot_number", "status",
            name="uq_inventory_location_unique_bin_item"
        ),
        CheckConstraint("quantity >= 0", name="check_inventory_location_quantity_positive"),
        CheckConstraint("allocated_qty >= 0", name="check_inventory_location_allocated_qty_positive"),
        CheckConstraint(
            "quantity >= allocated_qty", name="check_inventory_location_allocated_le_quantity"
        ),
        Index("ix_inv_loc_wh_prod_pos", "warehouse_id", "product_id", "position_id"),
        Index("ix_inv_loc_owner", "owner_id"),
        Index("ix_inv_loc_wh_owner_prod", "warehouse_id", "owner_id", "product_id"),
        Index("ix_inv_loc_prod_lpn", "product_id", "lpn"),
        Index("ix_inv_loc_prod_expiry", "warehouse_id", "product_id", "expiry_date"),
        Index("ix_inv_loc_lot", "lot_number"),
    )
