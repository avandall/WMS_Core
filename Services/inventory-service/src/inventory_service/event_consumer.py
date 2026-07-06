from __future__ import annotations

import os
import socket
import threading

from shared_utils.events import DurableRedisStreamConsumer, EventEnvelope, RedisStreamClient, get_publisher

from app.modules.inventory.application.services.inventory_service import InventoryService
from app.modules.inventory.infrastructure.repositories.inventory_repo import InventoryRepo
from app.shared.core.database import get_session
from app.shared.core.logging import get_logger


logger = get_logger(__name__)


class InventoryMovementConsumer:
    def handle(self, message_id: str, envelope: EventEnvelope) -> None:
        if envelope.type != "InventoryMovementRequested":
            return

        import warnings
        warnings.warn(
            "InventoryMovementRequested event type is deprecated. Use granular transaction/execution confirmations instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        logger.warning("Handling deprecated event type: InventoryMovementRequested")

        session_gen = get_session()
        db = next(session_gen)
        try:
            service = InventoryService(
                inventory_repo=InventoryRepo(db),
                event_publisher=get_publisher("inventory-service"),
            )
            payload = dict(envelope.payload)
            payload.setdefault("event_id", envelope.event_id)
            service.apply_document_movement(payload)
        finally:
            try:
                db.close()
            except Exception:
                logger.debug("Failed to close inventory consumer DB session", exc_info=True)


def start_inventory_movement_consumer_thread() -> threading.Thread | None:
    if os.getenv("INVENTORY_MOVEMENT_CONSUMER_ENABLED", "1") != "1":
        return None
    event_bus_url = os.getenv("EVENT_BUS_URL")
    if not event_bus_url:
        return None

    stream = os.getenv("EVENT_STREAM", "wms.events")
    consumer = DurableRedisStreamConsumer(
        client=RedisStreamClient(event_bus_url),
        stream=stream,
        group="inventory-service",
        consumer=f"inventory-{socket.gethostname()}",
        handler=InventoryMovementConsumer().handle,
        dlq_stream=os.getenv("INVENTORY_DLQ_STREAM", "wms.events.inventory.dlq"),
        max_attempts=int(os.getenv("INVENTORY_CONSUMER_MAX_ATTEMPTS", "3")),
        reclaim_idle_ms=int(os.getenv("INVENTORY_RECLAIM_IDLE_MS", "60000")),
    )

    def run() -> None:
        while True:
            try:
                consumer.poll_once()
            except Exception as exc:
                logger.error("Inventory movement consumer error: %s", exc)

    thread = threading.Thread(target=run, name="inventory-movement-consumer", daemon=True)
    thread.start()
    return thread
