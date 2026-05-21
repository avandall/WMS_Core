# Event Bus Baseline

Phase 11 replaces stdout-only placeholder events with a local Redis Streams bus.

## Broker

- Local broker: Redis Streams via the `event-bus` service in root `docker-compose.yml`.
- Stream: `wms.events`
- Shared env:
  - `EVENT_BUS_URL=redis://event-bus:6379/0`
  - `EVENT_STREAM=wms.events`
- Disable publishing with `EVENTS_ENABLED=0`.

## Envelope

Events are published as one JSON field named `event` in Redis Streams.

```json
{
  "event_id": "uuid",
  "schema_version": 1,
  "occurred_at": "2026-05-21T00:00:00+00:00",
  "source": "documents-service",
  "type": "DocumentUploaded",
  "payload": {}
}
```

`event_id` is the idempotency key for future durable consumers. Producers may pass one in the payload; otherwise the shared publisher creates a UUID.

## Published Events

- `DocumentUploaded`
- `DocumentPosted`
- `InventoryAdjusted`
- `InventoryListed`
- `InventoryByWarehouseListed`
- `InventoryQuantityRead`
- `ProductCreated`
- `ProductUpdated`
- `ProductDeleted`
- `WarehouseCreated`
- `WarehouseDeleted`

## Consumers

- `audit-service` starts an in-process Redis Stream consumer when `AUDIT_EVENT_CONSUMER_ENABLED=1`.
- The consumer writes received domain events into `audit_events` in the audit datastore.
- Reporting and AI consumers are intentionally follow-up work; Phase 12+ can add production observability and Phase 15 can harden deployment/runtime operations.
