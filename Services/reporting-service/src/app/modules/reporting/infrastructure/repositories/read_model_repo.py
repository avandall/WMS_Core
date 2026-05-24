from __future__ import annotations

from shared_utils.events import EventEnvelope
from sqlalchemy.orm import Session

from app.modules.reporting.infrastructure.models.read_model_event import ReportingReadModelEvent


class ReportingReadModelRepo:
    def __init__(self, db: Session):
        self.db = db

    def record_event(self, *, stream_id: str, envelope: EventEnvelope) -> bool:
        existing = (
            self.db.query(ReportingReadModelEvent)
            .filter(ReportingReadModelEvent.event_id == envelope.event_id)
            .one_or_none()
        )
        if existing:
            return False

        payload = dict(envelope.payload)
        self.db.add(
            ReportingReadModelEvent(
                event_id=envelope.event_id,
                stream_id=stream_id,
                event_type=envelope.type,
                source=envelope.source,
                entity_type=payload.get("entity_type"),
                entity_id=str(payload["entity_id"]) if payload.get("entity_id") is not None else None,
                occurred_at=envelope.occurred_at,
                payload=payload,
            )
        )
        return True
