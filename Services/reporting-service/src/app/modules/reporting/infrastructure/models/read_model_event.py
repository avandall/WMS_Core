from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.core.database import Base


class ReportingReadModelEvent(Base):
    __tablename__ = "reporting_read_model_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    event_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    stream_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    entity_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    occurred_at: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(tz=timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_reporting_read_model_event_type_entity", "event_type", "entity_type", "entity_id"),
    )
