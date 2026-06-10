from __future__ import annotations

import os
import threading
import time

from shared_utils.events import DurableRedisStreamConsumer, EventEnvelope, RedisStreamClient

from app.modules.customers.application.services.customer_service import CustomerService
from app.modules.customers.infrastructure.repositories.customer_repo import CustomerRepo
from app.shared.core.database import get_session
from app.shared.core.logging import get_logger

logger = get_logger(__name__)


class CustomerPurchaseConsumer:
    def handle(self, message_id: str, envelope: EventEnvelope) -> None:
        # DocumentUploaded for SALE carries customer_id + items with unit_price
        if envelope.type != "DocumentUploaded":
            return
        payload = dict(envelope.payload or {})
        doc_type = str(payload.get("doc_type") or "").upper()
        if doc_type != "SALE":
            return

        document_id = payload.get("document_id")
        customer_id = payload.get("customer_id")
        if not customer_id or not document_id:
            return

        items = list(payload.get("items") or [])
        total_value = sum(
            int(i.get("quantity", 0)) * float(i.get("unit_price", 0))
            for i in items
        )

        session_gen = get_session()
        db = next(session_gen)
        try:
            service = CustomerService(customer_repo=CustomerRepo(db))
            # Avoid duplicate records for the same document
            existing = service.purchases(int(customer_id))
            if any(p.get("document_id") == int(document_id) for p in existing):
                return
            service.record_purchase(
                customer_id=int(customer_id),
                document_id=int(document_id),
                total_value=total_value,
            )
            logger.info(
                "Recorded purchase customer=%s document=%s value=%.2f",
                customer_id, document_id, total_value,
            )
        except Exception as exc:
            logger.error("Failed to record purchase: %s", exc)
        finally:
            try:
                db.close()
            except Exception:
                pass


def start_customer_purchase_consumer_thread() -> threading.Thread | None:
    if os.getenv("CUSTOMER_PURCHASE_CONSUMER_ENABLED", "1") != "1":
        return None
    event_bus_url = os.getenv("EVENT_BUS_URL", "")
    if not event_bus_url:
        return None

    consumer = DurableRedisStreamConsumer(
        client=RedisStreamClient(event_bus_url),
        stream=os.getenv("EVENT_STREAM", "wms.events"),
        group="customer-service",
        consumer="customer-service-1",
        handler=CustomerPurchaseConsumer().handle,
        dlq_stream="wms.events.customer.dlq",
        max_attempts=3,
        reclaim_idle_ms=60000,
    )

    def run() -> None:
        while True:
            try:
                consumer.poll_once()
            except Exception as exc:
                logger.error("Customer purchase consumer error: %s", exc)
                time.sleep(2)

    thread = threading.Thread(target=run, name="customer-purchase-consumer", daemon=True)
    thread.start()
    return thread



def start_customer_purchase_consumer_thread() -> threading.Thread | None:
    if os.getenv("CUSTOMER_PURCHASE_CONSUMER_ENABLED", "1") != "1":
        return None
    event_bus_url = os.getenv("EVENT_BUS_URL", "")
    if not event_bus_url:
        return None

    consumer = DurableRedisStreamConsumer(
        client=RedisStreamClient(event_bus_url),
        stream=os.getenv("EVENT_STREAM", "wms.events"),
        group="customer-service",
        consumer="customer-service-1",
        handler=CustomerPurchaseConsumer().handle,
        dlq_stream="wms.events.customer.dlq",
        max_attempts=3,
        reclaim_idle_ms=60000,
    )

    def run() -> None:
        while True:
            try:
                consumer.poll_once()
            except Exception as exc:
                logger.error("Customer purchase consumer error: %s", exc)
                time.sleep(2)

    thread = threading.Thread(target=run, name="customer-purchase-consumer", daemon=True)
    thread.start()
    return thread
