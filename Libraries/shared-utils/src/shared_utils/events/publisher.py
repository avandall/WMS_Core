from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol


class EventPublisher(Protocol):
    def publish(self, *, event_type: str, payload: dict[str, Any]) -> None: ...


@dataclass(slots=True)
class StdoutEventPublisher:
    service: str

    def publish(self, *, event_type: str, payload: dict[str, Any]) -> None:
        record = {
            "ts": datetime.now(tz=timezone.utc).isoformat(),
            "service": self.service,
            "type": event_type,
            "payload": payload,
        }
        print(json.dumps(record, ensure_ascii=False))


def get_publisher(service: str) -> EventPublisher:
    # Placeholder for future Kafka/NATS/RabbitMQ.
    enabled = os.getenv("EVENTS_ENABLED", "1") == "1"
    if not enabled:
        return StdoutEventPublisher(service=service)  # still safe/no-op-ish
    return StdoutEventPublisher(service=service)

