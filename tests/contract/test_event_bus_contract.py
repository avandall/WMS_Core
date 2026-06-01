from __future__ import annotations

import json
import subprocess
from pathlib import Path

from shared_utils.events import EventEnvelope, build_event


ROOT_DIR = Path(__file__).resolve().parents[2]


def _compose_config() -> dict:
    result = subprocess.run(
        ["docker", "compose", "config", "--format", "json"],
        cwd=ROOT_DIR,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_compose_defines_redis_stream_event_bus() -> None:
    services = _compose_config()["services"]

    assert services["event-bus"]["image"] == "redis:7-alpine"
    assert services["documents-service"]["environment"]["EVENT_BUS_URL"] == "redis://event-bus:6379/0"
    assert services["documents-service"]["environment"]["EVENT_STREAM"] == "wms.events"
    assert services["audit-service"]["environment"]["AUDIT_EVENT_CONSUMER_ENABLED"] == "1"
    assert "event-bus" in services["audit-service"]["depends_on"]
    assert "event-bus" in services["documents-service"]["depends_on"]
    assert "event-bus" in services["inventory-service"]["depends_on"]


def test_event_envelope_has_version_and_idempotency_key() -> None:
    event = build_event(
        source="documents-service",
        event_type="DocumentUploaded",
        payload={"entity_type": "document", "entity_id": 42},
    )

    assert event.schema_version == 1
    assert event.event_id
    assert event.occurred_at
    assert EventEnvelope.from_json(event.to_json()) == event


def test_audit_consumer_is_wired_into_audit_grpc_server() -> None:
    source = (ROOT_DIR / "Services/audit-service/src/audit_service/grpc_server.py").read_text()

    assert "start_audit_event_consumer_thread()" in source
