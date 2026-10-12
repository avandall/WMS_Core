from datetime import datetime, timezone
from sqlalchemy import BigInteger, Column, DateTime, Float, ForeignKey, Integer, String, JSON
from sqlalchemy.orm import relationship
from app.shared.core.database import Base


class CartonPackageModel(Base):
    """SQLAlchemy model for persisting Pack Station cartons and weight verification results."""

    __tablename__ = "carton_packages"

    carton_id = Column(String(100), primary_key=True)
    order_id = Column(String(100), nullable=False, index=True)
    packaging_tare_weight_g = Column(Float, nullable=False, default=100.0)
    status = Column(String(50), nullable=False, default="PACKING", index=True)
    measured_weight_g = Column(Float, nullable=True)
    verification_result = Column(JSON, nullable=True)
    items = Column(JSON, nullable=False, default=list)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    manifest_items = relationship(
        "CartonManifestItemModel",
        back_populates="carton",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class CartonManifestItemModel(Base):
    """SQLAlchemy model linking carton package to individual order line items (Carton Manifest & GS1/SSCC)."""

    __tablename__ = "carton_manifest_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    carton_id = Column(
        String(100),
        ForeignKey("carton_packages.carton_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    package_id = Column(String(100), nullable=True, index=True)
    document_id = Column(Integer, nullable=True, index=True)
    product_id = Column(BigInteger, nullable=False, index=True)
    sku = Column(String(100), nullable=True, default="")
    quantity = Column(Integer, nullable=False)
    lot_number = Column(String(100), nullable=True, default="", index=True)
    unit_weight_g = Column(Float, nullable=False, default=0.0)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    carton = relationship("CartonPackageModel", back_populates="manifest_items")

