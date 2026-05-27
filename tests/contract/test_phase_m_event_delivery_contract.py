from __future__ import annotations

import importlib.util
from pathlib import Path

from shared_utils.events import build_event


ROOT_DIR = Path(__file__).resolve().parents[2]

_DRAIN_SPEC = importlib.util.spec_from_file_location("drain_dlq", ROOT_DIR / "scripts/drain_dlq.py")
assert _DRAIN_SPEC and _DRAIN_SPEC.loader
_DRAIN_MODULE = importlib.util.module_from_spec(_DRAIN_SPEC)
_DRAIN_SPEC.loader.exec_module(_DRAIN_MODULE)
drain_dlq = _DRAIN_MODULE.drain_dlq


def _read(relative_path: str) -> str:
    return (ROOT_DIR / relative_path).read_text()


def test_mutating_document_and_inventory_events_publish_after_commit() -> None:
    documents = _read(
        "Services/documents-service/src/app/modules/documents/application/services/document_service.py"
    )
    inventory = _read(
        "Services/inventory-service/src/app/modules/inventory/application/services/inventory_service.py"
    )

    assert documents.index("self._commit_if_needed()") < documents.index("self._publish_document_uploaded")
    assert documents.index("self._commit_if_needed()") < documents.index("self._publish_document_posted")
    assert documents.index("self._commit_if_needed()") < documents.index('event_type="DocumentCancelled"')

    for event_type in (
        "InventoryAdjusted",
        "StockReserved",
        "ReservationReleased",
        "InventoryMovementApplied",
    ):
        assert inventory.index("self._commit_if_needed()") < inventory.index(f'event_type="{event_type}"')


def test_catalog_and_warehouse_events_publish_after_application_commit() -> None:
    product_servicer = _read("Services/product-service/src/product_service/grpc_servicer.py")
    warehouse_servicer = _read("Services/warehouse-service/src/warehouse_service/grpc_servicer.py")

    assert product_servicer.index("service.create_product(") < product_servicer.index('event_type="ProductCreated"')
    assert product_servicer.index("service.update_product(") < product_servicer.index('event_type="ProductUpdated"')
    assert product_servicer.index("service.delete_product(product_id)") < product_servicer.index(
        'event_type="ProductDeleted"'
    )
    assert warehouse_servicer.index("service.create_warehouse(") < warehouse_servicer.index(
        'event_type="WarehouseCreated"'
    )
    assert warehouse_servicer.index("service.delete_warehouse(warehouse_id)") < warehouse_servicer.index(
        'event_type="WarehouseDeleted"'
    )


def test_dlq_drain_replay_tool_preserves_idempotency_metadata() -> None:
    drain = _read("scripts/drain_dlq.py")
    events = _read("docs/events.md")

    assert "--dlq-stream" in drain
    assert "--target-stream" in drain
    assert "replay_of_event_id" in drain
    assert "replay_of_dlq_stream" in drain
    assert "client.xadd(target_stream" in drain
    assert "scripts/drain_dlq.py" in events
    assert "wms.events.replay" in events


def test_dlq_drain_function_replays_with_metadata() -> None:
    class FakeClient:
        def __init__(self):
            self.added = []
            self.reads = 0

        def xread(self, stream, last_id, *, block_ms, count):
            self.reads += 1
            if self.reads > 1:
                return []
            return [
                (
                    "1-0",
                    build_event(
                        source="inventory-service",
                        event_type="InventoryAdjusted",
                        payload={"event_id": "adjust-1", "entity_type": "inventory"},
                    ),
                )
            ]

        def xadd(self, stream, envelope):
            self.added.append((stream, envelope))
            return "2-0"

    client = FakeClient()
    result = drain_dlq(
        client=client,
        dlq_stream="wms.events.inventory.dlq",
        target_stream="wms.events.replay",
        from_id="0-0",
        count=10,
        dry_run=False,
    )

    assert result == {"drained": 1}
    assert client.added[0][0] == "wms.events.replay"
    payload = client.added[0][1].payload
    assert payload["replay_of_event_id"]
    assert payload["replay_of_dlq_stream"] == "wms.events.inventory.dlq"
    assert payload["replay_of_dlq_stream_id"] == "1-0"


def test_phase_m_docs_define_ordering_and_remaining_outbox_boundary() -> None:
    plan = _read("docs/internal_architecture_refactor_plan.md")
    events = _read("docs/events.md")
    release_ops = _read("docs/release_ops.md")

    assert "## Phase M: Transactional Event Delivery Hardening" in plan
    assert "Status: DONE." in plan
    assert "Producer Delivery Guarantees" in events
    assert "Event Ordering" in events
    assert "publish-after-commit" in events
    assert "DLQ drain" in release_ops
