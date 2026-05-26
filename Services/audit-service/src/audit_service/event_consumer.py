from __future__ import annotations

import os
import threading
import time
from typing import Any

from shared_utils.events import DurableRedisStreamConsumer, EventEnvelope, RedisStreamClient

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


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


class AuditEventConsumer:
    def __init__(
        self,
        *,
        event_bus_url: str,
        stream: str,
        start_id: str = "$",
        block_ms: int = 5000,
        batch_size: int = 20,
        max_stream_length: int = 10000,
        group: str = "audit-service",
        consumer_name: str = "audit-service-1",
        dlq_stream: str = "wms.events.audit.dlq",
        max_attempts: int = 3,
        reclaim_idle_ms: int = 60000,
    ):
        self.client = RedisStreamClient(event_bus_url, timeout=max(block_ms / 1000 + 1, 2))
        self.stream = stream
        self.last_id = start_id
        self.block_ms = block_ms
        self.batch_size = batch_size
        self.max_stream_length = max_stream_length
        self.group = group
        self.consumer_name = consumer_name
        self.consumer = DurableRedisStreamConsumer(
            client=self.client,
            stream=stream,
            group=group,
            consumer=consumer_name,
            handler=self._ingest,
            dlq_stream=dlq_stream,
            block_ms=block_ms,
            batch_size=batch_size,
            max_attempts=max_attempts,
            reclaim_idle_ms=reclaim_idle_ms,
            group_start_id=start_id,
        )
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def run_forever(self) -> None:
        init_db()
        logger.info("Starting audit event consumer on stream %s", self.stream)
        while not self._stop.is_set():
            try:
                self._apply_backpressure()
                self.consumer.poll_once()
            except Exception as exc:
                logger.error("Audit event consumer error: %s", exc)
                time.sleep(2)

    def _apply_backpressure(self) -> None:
        if self.max_stream_length <= 0:
            return
        stream_length = self.client.xlen(self.stream)
        if stream_length <= self.max_stream_length:
            return
        logger.warning(
            "Audit event stream length %s exceeds max %s; backing off",
            stream_length,
            self.max_stream_length,
        )
        time.sleep(1)

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
                event_id=envelope.event_id,
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
        block_ms=_int_env("AUDIT_EVENT_CONSUMER_BLOCK_MS", 5000),
        batch_size=_int_env("AUDIT_EVENT_CONSUMER_BATCH_SIZE", 20),
        max_stream_length=_int_env("AUDIT_EVENT_CONSUMER_MAX_STREAM_LENGTH", 10000),
        group=os.getenv("AUDIT_EVENT_CONSUMER_GROUP", "audit-service"),
        consumer_name=os.getenv("AUDIT_EVENT_CONSUMER_NAME", "audit-service-1"),
        dlq_stream=os.getenv("AUDIT_EVENT_DLQ_STREAM", "wms.events.audit.dlq"),
        max_attempts=_int_env("AUDIT_EVENT_CONSUMER_MAX_ATTEMPTS", 3),
        reclaim_idle_ms=_int_env("AUDIT_EVENT_CONSUMER_RECLAIM_IDLE_MS", 60000),
    )
    thread = threading.Thread(target=consumer.run_forever, name="audit-event-consumer", daemon=True)
    thread.start()
    return thread
