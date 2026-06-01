from __future__ import annotations

import os
import threading
import time

from shared_utils.events import DurableRedisStreamConsumer, EventEnvelope, RedisStreamClient

from app.modules.reporting.infrastructure.repositories.read_model_repo import ReportingReadModelRepo
from app.shared.core.database import SessionLocal, init_db
from app.shared.core.logging import get_logger


logger = get_logger(__name__)


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


class ReportingReadModelConsumer:
    def __init__(
        self,
        *,
        event_bus_url: str,
        stream: str,
        group: str = "reporting-service",
        consumer_name: str = "reporting-service-1",
        dlq_stream: str = "wms.events.reporting.dlq",
        block_ms: int = 5000,
        batch_size: int = 20,
        max_attempts: int = 3,
        reclaim_idle_ms: int = 60000,
        group_start_id: str = "0",
    ):
        self.consumer = DurableRedisStreamConsumer(
            client=RedisStreamClient(event_bus_url, timeout=max(block_ms / 1000 + 1, 2)),
            stream=stream,
            group=group,
            consumer=consumer_name,
            handler=self._ingest,
            dlq_stream=dlq_stream,
            block_ms=block_ms,
            batch_size=batch_size,
            max_attempts=max_attempts,
            reclaim_idle_ms=reclaim_idle_ms,
            group_start_id=group_start_id,
        )
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def run_forever(self) -> None:
        init_db()
        logger.info("Starting reporting read-model consumer")
        while not self._stop.is_set():
            try:
                self.consumer.poll_once()
            except Exception as exc:
                logger.error("Reporting read-model consumer error: %s", exc)
                time.sleep(2)

    def _ingest(self, message_id: str, envelope: EventEnvelope) -> None:
        db = SessionLocal()
        try:
            repo = ReportingReadModelRepo(db)
            repo.record_event(stream_id=message_id, envelope=envelope)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()


def start_reporting_read_model_consumer_thread() -> threading.Thread | None:
    if os.getenv("REPORTING_READ_MODEL_CONSUMER_ENABLED", "1") != "1":
        return None
    event_bus_url = os.getenv("EVENT_BUS_URL", "")
    if not event_bus_url:
        return None

    consumer = ReportingReadModelConsumer(
        event_bus_url=event_bus_url,
        stream=os.getenv("EVENT_STREAM", "wms.events"),
        group=os.getenv("REPORTING_READ_MODEL_CONSUMER_GROUP", "reporting-service"),
        consumer_name=os.getenv("REPORTING_READ_MODEL_CONSUMER_NAME", "reporting-service-1"),
        dlq_stream=os.getenv("REPORTING_READ_MODEL_DLQ_STREAM", "wms.events.reporting.dlq"),
        block_ms=_int_env("REPORTING_READ_MODEL_CONSUMER_BLOCK_MS", 5000),
        batch_size=_int_env("REPORTING_READ_MODEL_CONSUMER_BATCH_SIZE", 20),
        max_attempts=_int_env("REPORTING_READ_MODEL_CONSUMER_MAX_ATTEMPTS", 3),
        reclaim_idle_ms=_int_env("REPORTING_READ_MODEL_CONSUMER_RECLAIM_IDLE_MS", 60000),
        group_start_id=os.getenv("REPORTING_READ_MODEL_CONSUMER_START_ID", "0"),
    )
    thread = threading.Thread(target=consumer.run_forever, name="reporting-read-model-consumer", daemon=True)
    thread.start()
    return thread
