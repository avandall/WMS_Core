# Backup, Restore, and Disaster Recovery

Phase R defines how the service-owned datastore model is restored after data loss, regional
failure, or a bad release that requires full recovery.

## Backup Ownership

| Component | Owner | Retention | Encryption | Restore order |
| --- | --- | --- | --- | --- |
| `identity-service` datastore | identity-service | 35d | required | 1 |
| `customer-service` datastore | customer-service | 35d | required | 2 |
| `product-service` datastore | product-service | 35d | required | 3 |
| `warehouse-service` datastore | warehouse-service | 35d | required | 4 |
| `inventory-service` datastore | inventory-service | 35d | required | 5 |
| `documents-service` datastore | documents-service | 35d | required | 6 |
| `audit-service` datastore | audit-service | 90d | required | 7 |
| `reporting-service` datastore | reporting-service | 14d | required | 8 |

Reporting is recoverable from event replay, so its datastore backup is useful for faster restore
but not the only recovery path.

## Redis Streams

Back up Redis persistence or managed-service snapshots for:

- `wms.events`
- `wms.events.replay`
- `wms.events.audit.dlq`
- `wms.events.inventory.dlq`
- `wms.events.reporting.dlq`
- `wms.events.ai.dlq`

Every restore record must include stream snapshot IDs and the event offsets used for replay.
Consumers must resume from known offsets and rely on idempotency ledgers for duplicate delivery.

## RPO/RTO Targets

| Workflow | RPO | RTO |
| --- | --- | --- |
| auth/login | 15m | 30m |
| document posting | 15m | 60m |
| inventory reconciliation | 15m | 60m |
| reporting rebuild | 60m | 4h |

## Restore Rehearsal

Use `deploy/kubernetes/examples/disaster-recovery-manifest.example.json` as the rehearsal record.
It captures datastore snapshots, Redis stream offsets, restore order, RPO/RTO targets, and
validation checks.

Validate the manifest only:

```bash
python3 scripts/dr_rehearsal.py \
  --manifest deploy/kubernetes/examples/disaster-recovery-manifest.example.json \
  --dry-run
```

Run against disposable SQLite restore databases:

```bash
python3 scripts/dr_rehearsal.py --manifest /tmp/wms-dr/rehearsal.json
```

The local checker supports `sqlite:///` rehearsal URLs. Production restore should use the same
manifest/check shape with the platform backup tooling for the real database engines.

## Restore Order

1. Freeze traffic at the API Gateway or route traffic away from the damaged environment.
2. Restore service datastores from encrypted snapshots.
3. Restore Redis stream snapshots and capture replay offsets.
4. Start `identity-service` first so auth checks can run.
5. Start customer, product, and warehouse services.
6. Start documents and inventory services.
7. Replay `wms.events` or `wms.events.replay` to the recorded offset.
8. Rebuild reporting projections from events.
9. Start API Gateway and run smoke checks.

## Validation Checks

Recovery is not complete until these checks pass:

- auth works with restored users
- document posting is not duplicated after replay
- inventory totals reconcile against the restored movement ledger
- reporting projections can be rebuilt from restored streams
- DLQ streams are either empty or have a documented drain/replay decision

## Rollback and Roll-Forward

If validation fails, choose one path:

- Roll back to the previous release artifact and database snapshots.
- Roll forward by fixing the affected service and replaying from the captured stream offset.

Record the chosen path, snapshot IDs, event offsets, release artifact, and validation output in the
incident ticket before returning traffic to normal.
