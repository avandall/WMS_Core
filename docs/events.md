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

- `audit-service` starts an in-process Redis Stream consumer group when
  `AUDIT_EVENT_CONSUMER_ENABLED=1`.
- The consumer writes received domain events into `audit_events` in the audit datastore.
- `reporting-service` starts an idempotent read-model consumer when
  `REPORTING_READ_MODEL_CONSUMER_ENABLED=1`. It stores event envelopes in
  `reporting_read_model_events` with a unique `event_id`.
- `ai-service` remains opt-in and can start an AI reindex queue consumer when both the compose
  `ai` profile and `AI_REINDEX_CONSUMER_ENABLED=1` are enabled.

## Durable Processing

Phase 18 uses Redis consumer groups for durable async workflows:

- Consumer group names are service-owned, for example `audit-service` and `reporting-service`.
- Failed messages remain pending and can be reclaimed after `*_RECLAIM_IDLE_MS`.
- Messages that exceed `*_MAX_ATTEMPTS` are copied to service-owned DLQ streams:
  - `wms.events.audit.dlq`
  - `wms.events.reporting.dlq`
  - `wms.events.ai.dlq`
- Consumers acknowledge messages only after the service-owned datastore or queue write commits.

## Replay

Use `scripts/replay_events.py` for event replay planning and backfill:

```bash
PYTHONPATH=Libraries/shared-utils/src python3 scripts/replay_events.py \
  --event-bus-url redis://localhost:6379/0 \
  --stream wms.events \
  --from-id 0-0 \
  --target-stream wms.events.replay \
  --dry-run
```

The replay tool preserves `event_id` for idempotency verification and adds replay metadata
to the payload.
