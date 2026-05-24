from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

from shared_utils.events import DurableRedisStreamConsumer, EventEnvelope, RedisStreamClient


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


class AIReindexConsumer:
    def __init__(
        self,
        *,
        event_bus_url: str,
        stream: str,
        queue_path: str,
        group: str = "ai-service",
        consumer_name: str = "ai-service-1",
        dlq_stream: str = "wms.events.ai.dlq",
        block_ms: int = 5000,
        batch_size: int = 10,
        max_attempts: int = 3,
        reclaim_idle_ms: int = 60000,
        group_start_id: str = "0",
    ):
        self.queue_path = Path(queue_path)
        self.consumer = DurableRedisStreamConsumer(
            client=RedisStreamClient(event_bus_url, timeout=max(block_ms / 1000 + 1, 2)),
            stream=stream,
            group=group,
            consumer=consumer_name,
            handler=self._enqueue_reindex,
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
        self.queue_path.parent.mkdir(parents=True, exist_ok=True)
        while not self._stop.is_set():
            try:
                self.consumer.poll_once()
            except Exception:
                time.sleep(2)

    def _enqueue_reindex(self, message_id: str, envelope: EventEnvelope) -> None:
        payload = {
            "event_id": envelope.event_id,
            "event_type": envelope.type,
            "stream_id": message_id,
            "source": envelope.source,
            "occurred_at": envelope.occurred_at,
            "payload": envelope.payload,
        }
        with self.queue_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def start_ai_reindex_consumer_thread() -> threading.Thread | None:
    if os.getenv("AI_REINDEX_CONSUMER_ENABLED", "0") != "1":
        return None
    event_bus_url = os.getenv("EVENT_BUS_URL", "")
    if not event_bus_url:
        return None

    consumer = AIReindexConsumer(
        event_bus_url=event_bus_url,
        stream=os.getenv("EVENT_STREAM", "wms.events"),
        queue_path=os.getenv("AI_REINDEX_QUEUE_PATH", "/tmp/wms-ai-reindex-queue.jsonl"),
        group=os.getenv("AI_REINDEX_CONSUMER_GROUP", "ai-service"),
        consumer_name=os.getenv("AI_REINDEX_CONSUMER_NAME", "ai-service-1"),
        dlq_stream=os.getenv("AI_REINDEX_DLQ_STREAM", "wms.events.ai.dlq"),
        block_ms=_int_env("AI_REINDEX_CONSUMER_BLOCK_MS", 5000),
        batch_size=_int_env("AI_REINDEX_CONSUMER_BATCH_SIZE", 10),
        max_attempts=_int_env("AI_REINDEX_CONSUMER_MAX_ATTEMPTS", 3),
        reclaim_idle_ms=_int_env("AI_REINDEX_CONSUMER_RECLAIM_IDLE_MS", 60000),
        group_start_id=os.getenv("AI_REINDEX_CONSUMER_START_ID", "0"),
    )
    thread = threading.Thread(target=consumer.run_forever, name="ai-reindex-consumer", daemon=True)
    thread.start()
    return thread
