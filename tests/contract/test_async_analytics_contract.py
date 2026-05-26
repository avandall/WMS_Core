from __future__ import annotations

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (ROOT_DIR / relative_path).read_text()


def test_shared_events_support_consumer_groups_retry_and_dlq() -> None:
    source = _read("Libraries/shared-utils/src/shared_utils/events/publisher.py")
    exports = _read("Libraries/shared-utils/src/shared_utils/events/__init__.py")

    assert "class DurableRedisStreamConsumer" in source
    assert "XGROUP" in source
    assert "XREADGROUP" in source
    assert "XAUTOCLAIM" in source
    assert "XPENDING" in source
    assert "XACK" in source
    assert "dlq_stream" in source
    assert "max_attempts" in source
    assert "DurableRedisStreamConsumer" in exports


def test_audit_inventory_reporting_and_ai_consumers_use_durable_groups() -> None:
    audit = _read("Services/audit-service/src/audit_service/event_consumer.py")
    inventory = _read("Services/inventory-service/src/inventory_service/event_consumer.py")
    reporting = _read("Services/reporting-service/src/reporting_service/event_consumer.py")
    ai = _read("Services/ai-service/src/ai_service/event_consumer.py")

    assert "DurableRedisStreamConsumer" in audit
    assert "AUDIT_EVENT_CONSUMER_GROUP" in audit
    assert "AUDIT_EVENT_DLQ_STREAM" in audit
    assert "DurableRedisStreamConsumer" in inventory
    assert "INVENTORY_DLQ_STREAM" in inventory
    assert "InventoryMovementRequested" in inventory
    assert "DurableRedisStreamConsumer" in reporting
    assert "REPORTING_READ_MODEL_CONSUMER_GROUP" in reporting
    assert "REPORTING_READ_MODEL_DLQ_STREAM" in reporting
    assert "DurableRedisStreamConsumer" in ai
    assert "AI_REINDEX_CONSUMER_ENABLED" in ai
    assert "AI_REINDEX_QUEUE_PATH" in ai


def test_reporting_read_model_is_service_owned_and_idempotent() -> None:
    model = _read(
        "Services/reporting-service/src/app/modules/reporting/infrastructure/models/read_model_event.py"
    )
    repo = _read(
        "Services/reporting-service/src/app/modules/reporting/infrastructure/repositories/read_model_repo.py"
    )
    database = _read("Services/reporting-service/src/app/shared/core/database.py")
    compose = _read("docker-compose.yml")

    assert "__tablename__ = \"reporting_read_model_events\"" in model
    assert "event_id" in model
    assert "unique=True" in model
    assert "ReportingReadModelEvent.event_id == envelope.event_id" in repo
    assert "record_event" in repo
    assert "app.modules.reporting.infrastructure.models.read_model_event" in database
    assert "reporting_read_model_events" in compose


def test_replay_tool_preserves_idempotency_metadata() -> None:
    source = _read("scripts/replay_events.py")

    assert "--dry-run" in source
    assert "--target-stream" in source
    assert "seen_event_ids" in source
    assert "replay_of_event_id" in source
    assert "client.xadd(target_stream" in source


def test_phase_18_docs_and_runtime_config_are_complete() -> None:
    events = _read("docs/events.md")
    roadmap = _read("docs/roadmap.md")
    configmap = _read("deploy/kubernetes/base/configmap.yaml")

    assert "Phase 18: Advanced Async/Analytics Workflows — DONE" in roadmap
    assert "wms.events.audit.dlq" in events
    assert "wms.events.inventory.dlq" in events
    assert "wms.events.reporting.dlq" in events
    assert "wms.events.ai.dlq" in events
    assert "scripts/replay_events.py" in events
    assert "REPORTING_READ_MODEL_CONSUMER_ENABLED: \"1\"" in configmap
    assert "AI_REINDEX_CONSUMER_ENABLED: \"0\"" in configmap
