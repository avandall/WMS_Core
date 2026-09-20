from __future__ import annotations

from sqlalchemy import BigInteger, Column, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.shared.core.database import Base


class ProductUomModel(Base):
    __tablename__ = "product_uoms"

    uom_id = Column(BigInteger, primary_key=True, autoincrement=True)
    product_id = Column(
        BigInteger, ForeignKey("products.product_id", ondelete="CASCADE"), nullable=False
    )
    uom_code = Column(String(20), nullable=False)
    conversion_factor = Column(Float, nullable=False, default=1.0)
    to_uom_code = Column(String(20), nullable=False, default="EACH")

    product = relationship("ProductModel", back_populates="uoms")

    __table_args__ = (
        UniqueConstraint("product_id", "uom_code", name="uq_product_uom_code"),
    )
