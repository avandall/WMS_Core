from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.core.database import Base


def utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class InventorySummary(Base):
    __tablename__ = "inventory_summary"

    product_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    total_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warehouse_quantities: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class DocumentSummary(Base):
    __tablename__ = "document_summary"

    document_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    doc_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    customer_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    from_warehouse_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    to_warehouse_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    total_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_value: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    created_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    posted_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class SalesSummary(Base):
    __tablename__ = "sales_summary"

    document_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    total_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_value: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class WarehouseActivitySummary(Base):
    __tablename__ = "warehouse_activity_summary"

    warehouse_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    movement_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_quantity_delta: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_document_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
