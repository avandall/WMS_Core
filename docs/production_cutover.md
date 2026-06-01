# Production Data Cutover and Backfill

Phase P proves the gRPC microservice stack can take over real data with a repeatable rehearsal,
reconciliation report, and rollback record.

## Source To Target Map

| Source data | Target owner | Cutover mode |
| --- | --- | --- |
| users/auth data | `identity-service` | migrate |
| customers | `customer-service` | migrate |
| products/SKUs | `product-service` | migrate |
| warehouses/positions/locations | `warehouse-service` | migrate |
| inventory balances and movement history | `inventory-service` | migrate |
| documents and document items | `documents-service` | migrate |
| audit history | `audit-service` | migrate |
| reporting projections | `reporting-service` | rebuild from `wms.events` and `wms.events.replay` |
| AI/vector examples | `ai-service` | optional rebuild from projection snapshots/events |

## Rehearsal Manifest

Use `deploy/kubernetes/examples/production-cutover-manifest.example.json` as the starting point.
It records:

- source and target datastore aliases
- service-owned target tables
- cutover order and read-only window
- row-count, orphan-reference, total, and freshness checks
- rollback database snapshots, event offsets, and release images

Validate the manifest without opening databases:

```bash
python3 scripts/cutover_rehearsal.py \
  --manifest deploy/kubernetes/examples/production-cutover-manifest.example.json \
  --dry-run
```

Run against disposable SQLite rehearsal databases:

```bash
python3 scripts/cutover_rehearsal.py --manifest /tmp/wms-cutover/rehearsal.json
```

The local checker intentionally supports `sqlite:///` URLs only. For PostgreSQL production
cutovers, keep the same manifest/check structure and run equivalent SQL through the platform's
approved migration runner.

## Cutover Order

1. Build immutable release images and record `RELEASE_VERSION`.
2. Capture source database snapshots and Redis stream IDs for `wms.events` and
   `wms.events.replay`.
3. Enter the read-only window for writes that affect users, documents, and inventory.
4. Run service-owned migrations from `deploy/kubernetes/examples/migration-jobs.yaml`.
5. Load service-owned target datastores.
6. Rebuild reporting projections by replaying events:

```bash
PYTHONPATH=Libraries/shared-utils/src python3 scripts/replay_events.py \
  --event-bus-url "$EVENT_BUS_URL" \
  --stream wms.events \
  --from-id "$CUTOVER_EVENT_FROM_ID" \
  --to-id "$CUTOVER_EVENT_TO_ID" \
  --target-stream wms.events.replay \
  --dry-run
```

7. Rebuild AI only when the `ai` profile is explicitly enabled, using events or projection
   snapshots rather than operational service databases.
8. Run reconciliation and resolve failures before traffic shift.
9. Shift traffic to API Gateway and run release smoke/load gates.

## Reconciliation Coverage

The reconciliation report must include:

- row counts for every service-owned target table
- orphan references for document items, inventory warehouse/product references, and movement
  ledger references
- document amount totals and inventory quantity totals
- reporting projection freshness and replay stream lag
- DLQ depth for audit, reporting, inventory, and AI streams

## Rollback Record

Every cutover rehearsal and real cutover must record:

- git SHA and release image tags for gateway and all non-AI services
- database snapshot identifiers for source and each target datastore
- Redis stream IDs for `wms.events`, `wms.events.replay`, and service-owned DLQ streams
- migration commands that were applied
- reconciliation output and unresolved exceptions

Rollback starts by routing traffic away from the new API Gateway, then restoring target databases
or returning to the previous runtime from the recorded release images and snapshots.
