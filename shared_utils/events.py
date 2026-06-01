"""Event utilities for contract tests."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict
import uuid


@dataclass
class EventEnvelope:
    """Event envelope with versioning and idempotency."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    schema_version: int = 1
    source: str = ""
    event_type: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    def to_json(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "event_id": self.event_id,
            "schema_version": self.schema_version,
            "source": self.source,
            "event_type": self.event_type,
            "payload": self.payload,
            "occurred_at": self.occurred_at.isoformat(),
        }

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "EventEnvelope":
        """Create from JSON data."""
        return cls(
            event_id=data.get("event_id", str(uuid.uuid4())),
            schema_version=data.get("schema_version", 1),
            source=data.get("source", ""),
            event_type=data.get("event_type", ""),
            payload=data.get("payload", {}),
            occurred_at=datetime.fromisoformat(data.get("occurred_at", datetime.utcnow().isoformat())),
        )


def build_event(
    source: str,
    event_type: str,
    payload: Dict[str, Any],
) -> EventEnvelope:
    """Build an event envelope."""
    return EventEnvelope(
        source=source,
        event_type=event_type,
        payload=payload,
    )
