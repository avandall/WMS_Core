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

## Producer Delivery Guarantees

Mutating producers use a publish-after-commit boundary: service state is committed before the
domain event is sent to Redis Streams. This prevents downstream consumers from seeing events for
transactions that later roll back.

Current producer boundary:

- `documents-service` commits document lifecycle changes before publishing document and inventory
  movement events.
- `inventory-service` records movement idempotency before publishing inventory movement events.
- `product-service` and `warehouse-service` publish catalog/warehouse events after the
  application service commits the owned datastore change.

If a future producer needs stronger crash recovery between commit and publish, add a
service-owned transactional outbox table for that service and drain it to `wms.events`.

## Event Ordering

Ordering is per aggregate/event key, not global:

- Document lifecycle events are ordered by `document_id`.
- Inventory movement application is ordered by source `event_id`.
- Catalog and warehouse CRUD events are ordered by `product_id` and `warehouse_id`.
- Consumers must still be idempotent because replay and DLQ drain can redeliver an older event.

## Published Events

- `DocumentUploaded`
- `DocumentPosted`
- `DocumentCancelled`
- `InventoryMovementRequested`
- `InventoryAdjusted`
- `StockReserved`
- `ReservationReleased`
- `InventoryMovementApplied`
- `InventoryListed`
- `InventoryByWarehouseListed`
- `InventoryQuantityRead`
- `ProductCreated`
- `ProductUpdated`
- `ProductDeleted`
- `WarehouseCreated`
- `WarehouseDeleted`

## Event Schemas

The contract fixture source is `tests/fixtures/event_contracts.json`. Each entry defines the
owning source service, required payload fields, and one valid fixture payload. Contract tests
assert that this fixture set exactly matches the published event list above.

Current required payload fields:

| Event | Source | Required payload fields |
| --- | --- | --- |
| `DocumentUploaded` | `documents-service` | `entity_type`, `entity_id`, `document_id`, `doc_type`, `status`, `items` |
| `DocumentPosted` | `documents-service` | `entity_type`, `entity_id`, `document_id`, `doc_type`, `status`, `approved_by` |
| `DocumentCancelled` | `documents-service` | `entity_type`, `entity_id`, `document_id`, `doc_type`, `status`, `cancelled_by` |
| `InventoryMovementRequested` | `documents-service` | `entity_type`, `entity_id`, `document_id`, `doc_type`, `items` |
| `InventoryAdjusted` | `inventory-service` | `entity_type`, `entity_id`, `product_id`, `quantity_delta` |
| `StockReserved` | `inventory-service` | `entity_type`, `entity_id`, `product_id`, `quantity` |
| `ReservationReleased` | `inventory-service` | `entity_type`, `entity_id`, `product_id`, `quantity` |
| `InventoryMovementApplied` | `inventory-service` | `entity_type`, `entity_id`, `document_id`, `doc_type`, `items` |
| `InventoryListed` | `inventory-service` | `entity_type`, `count` |
| `InventoryByWarehouseListed` | `inventory-service` | `entity_type`, `count` |
| `InventoryQuantityRead` | `inventory-service` | `entity_type`, `entity_id`, `product_id`, `quantity` |
| `ProductCreated` | `product-service` | `entity_type`, `entity_id`, `product_id` |
| `ProductUpdated` | `product-service` | `entity_type`, `entity_id`, `product_id` |
| `ProductDeleted` | `product-service` | `entity_type`, `entity_id`, `product_id` |
| `WarehouseCreated` | `warehouse-service` | `entity_type`, `entity_id`, `warehouse_id`, `location` |
| `WarehouseDeleted` | `warehouse-service` | `entity_type`, `entity_id`, `warehouse_id` |

## Breaking Change Policy

- Additive fields are allowed when consumers can ignore them and contract fixtures are updated.
- Removing or renaming a required payload field is breaking.
- Changing the meaning or type of a required field is breaking.
- Breaking changes require a new event type or a versioned consumer path using
  `schema_version`.
- Consumers must tolerate older `schema_version` values and unknown additive fields unless a
  versioned consumer path explicitly rejects them.

## Consumers

`documents-service` owns document lifecycle events. `DocumentUploaded`, `DocumentPosted`, and
`DocumentCancelled` describe document state changes. `InventoryMovementRequested` is emitted
after posting so `inventory-service` can apply stock movement idempotently without
`documents-service` writing inventory tables.
- `inventory-service` consumes `InventoryMovementRequested`, records the source event in
  `inventory_movement_ledger`, and emits `InventoryMovementApplied` after stock changes commit.

- `audit-service` starts an in-process Redis Stream consumer group when
  `AUDIT_EVENT_CONSUMER_ENABLED=1`.
- The consumer writes received domain events into `audit_events` in the audit datastore.
- `reporting-service` starts an idempotent read-model consumer when
  `REPORTING_READ_MODEL_CONSUMER_ENABLED=1`. It stores event envelopes in
  `reporting_read_model_events` with a unique `event_id`.
- `ai-service` remains opt-in and can start an AI reindex queue consumer when both the compose
  `ai` profile and `AI_REINDEX_CONSUMER_ENABLED=1` are enabled. The consumer converts event
  envelopes or projection snapshots into AI-owned reindex jobs, including `source_event_id`,
  `stream_id`, and optional `replay_of_event_id` so reindex can be replayed without reading
  operational service databases.

## Durable Processing

Phase 18 uses Redis consumer groups for durable async workflows:

- Consumer group names are service-owned, for example `audit-service` and `reporting-service`.
- Failed messages remain pending and can be reclaimed after `*_RECLAIM_IDLE_MS`.
- Messages that exceed `*_MAX_ATTEMPTS` are copied to service-owned DLQ streams:
  - `wms.events.audit.dlq`
  - `wms.events.inventory.dlq`
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

## DLQ Drain

Use `scripts/drain_dlq.py` to move a service-owned DLQ stream into the replay stream after the
underlying handler issue is fixed:

```bash
PYTHONPATH=Libraries/shared-utils/src python3 scripts/drain_dlq.py \
  --event-bus-url redis://localhost:6379/0 \
  --dlq-stream wms.events.inventory.dlq \
  --target-stream wms.events.replay \
  --dry-run
```

The drain tool adds `replay_of_event_id`, `replay_of_dlq_stream`, and
`replay_of_dlq_stream_id` metadata so consumers can preserve idempotency.

## Disaster Recovery

Redis stream snapshots and restore offsets are part of the disaster recovery record. See
`docs/disaster_recovery.md` and `deploy/kubernetes/examples/disaster-recovery-manifest.example.json`
for the expected `wms.events`, `wms.events.replay`, and service-owned DLQ stream evidence.
