from __future__ import annotations

import os
import threading
import time
from typing import Any

from shared_utils.events import EventEnvelope, RedisStreamClient

from app.modules.audit.infrastructure.repositories.audit_event_repo import AuditEventRepo
from app.shared.core.database import SessionLocal, init_db
from app.shared.core.logging import get_logger


logger = get_logger(__name__)


def _int_or_none(value: Any) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


class AuditEventConsumer:
    def __init__(
        self,
        *,
        event_bus_url: str,
        stream: str,
        start_id: str = "$",
        block_ms: int = 5000,
        batch_size: int = 20,
    ):
        self.client = RedisStreamClient(event_bus_url, timeout=max(block_ms / 1000 + 1, 2))
        self.stream = stream
        self.last_id = start_id
        self.block_ms = block_ms
        self.batch_size = batch_size
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def run_forever(self) -> None:
        init_db()
        logger.info("Starting audit event consumer on stream %s", self.stream)
        while not self._stop.is_set():
            try:
                for message_id, envelope in self.client.xread(
                    self.stream,
                    self.last_id,
                    block_ms=self.block_ms,
                    count=self.batch_size,
                ):
                    self._ingest(message_id, envelope)
                    self.last_id = message_id
            except Exception as exc:
                logger.error("Audit event consumer error: %s", exc)
                time.sleep(2)

    def _ingest(self, message_id: str, envelope: EventEnvelope) -> None:
        payload = dict(envelope.payload)
        payload.setdefault("event_id", envelope.event_id)
        payload.setdefault("event_stream_id", message_id)
        payload.setdefault("event_source", envelope.source)
        payload.setdefault("event_type", envelope.type)
        payload.setdefault("event_schema_version", envelope.schema_version)
        payload.setdefault("event_occurred_at", envelope.occurred_at)

        db = SessionLocal()
        try:
            repo = AuditEventRepo(db)
            repo.create_event(
                action=envelope.type,
                entity_type=payload.get("entity_type"),
                entity_id=str(payload["entity_id"]) if payload.get("entity_id") is not None else None,
                warehouse_id=_int_or_none(payload.get("warehouse_id")),
                user_id=_int_or_none(payload.get("user_id")),
                payload=payload,
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()


def start_audit_event_consumer_thread() -> threading.Thread | None:
    if os.getenv("AUDIT_EVENT_CONSUMER_ENABLED", "1") != "1":
        return None
    event_bus_url = os.getenv("EVENT_BUS_URL", "")
    if not event_bus_url:
        return None

    consumer = AuditEventConsumer(
        event_bus_url=event_bus_url,
        stream=os.getenv("EVENT_STREAM", "wms.events"),
        start_id=os.getenv("AUDIT_EVENT_CONSUMER_START_ID", "$"),
    )
    thread = threading.Thread(target=consumer.run_forever, name="audit-event-consumer", daemon=True)
    thread.start()
    return thread
