# Release, Deployment, and Ops Baseline

Phase 15 defines the release/ops contract for the gRPC-first microservice stack. Phase 17
adds the first deployment artifact baseline under `deploy/kubernetes`.

## Release Identity

Use one immutable release id for every image in the stack:

```bash
export RELEASE_VERSION="$(git rev-parse --short=12 HEAD)"
```

Images follow this naming convention:

| Component | Local image | Release tag |
| --- | --- | --- |
| API Gateway | `wms/api-gateway:dev` | `wms/api-gateway:$RELEASE_VERSION` |
| Identity | `wms/identity-service:dev` | `wms/identity-service:$RELEASE_VERSION` |
| Customer | `wms/customer-service:dev` | `wms/customer-service:$RELEASE_VERSION` |
| Product | `wms/product-service:dev` | `wms/product-service:$RELEASE_VERSION` |
| Warehouse | `wms/warehouse-service:dev` | `wms/warehouse-service:$RELEASE_VERSION` |
| Inventory | `wms/inventory-service:dev` | `wms/inventory-service:$RELEASE_VERSION` |
| Documents | `wms/documents-service:dev` | `wms/documents-service:$RELEASE_VERSION` |
| Audit | `wms/audit-service:dev` | `wms/audit-service:$RELEASE_VERSION` |
| Reporting | `wms/reporting-service:dev` | `wms/reporting-service:$RELEASE_VERSION` |
| AI | `wms/ai-service:dev` | `wms/ai-service:$RELEASE_VERSION` |

Default dev/test release validation does not build AI. AI remains an explicit profile:

```bash
docker compose --profile ai build ai-service
```

## Build And SBOM

Baseline build:

```bash
docker compose build api-gateway identity-service customer-service product-service warehouse-service inventory-service documents-service audit-service reporting-service
```

Recommended SBOM command when `syft` is available:

```bash
syft wms/api-gateway:$RELEASE_VERSION -o spdx-json > sbom-api-gateway.spdx.json
```

Every production release should attach one SBOM per image and record the git SHA,
`uv.lock` hash, and generated proto commit.

## CI/CD Release Enforcement

Release gates are automated in `.github/workflows/release-gates.yml`.

Pull requests and pushes validate:

- default contract tests
- gateway E2E smoke through `tests/e2e/run_gateway_stack_tests.sh`
- `docker compose config --quiet`
- `kubectl kustomize deploy/kubernetes/base`
- generated proto drift through `scripts/gen_protos.py` and `git diff --exit-code`
- production cutover manifest dry-run

Release candidates additionally build all non-AI runtime images, keep the AI image behind the
explicit `run_ai_image` workflow input, generate SBOM output, run a vulnerability scan, and upload
`release-artifact.json`.

Release artifact command:

```bash
python3 scripts/release_artifact.py --release-version "$RELEASE_VERSION" --output release-artifact.json
```

Artifact format and retention expectations are documented in `docs/release_artifact.md`.

## Deployment Contract

Minimum platform requirements:

- A secret manager provides `SECRET_KEY`, database credentials, and gRPC mTLS certs.
- Each service gets its own datastore connection.
- API Gateway is the only public REST entrypoint.
- gRPC service ports are private inside the cluster/network.
- Redis Streams is available as `event-bus`.
- `/health` and `/metrics` are scraped for gateway and services.

Deployment package:

- Kubernetes base: `deploy/kubernetes/base`
- Secret/cert placeholders: `deploy/kubernetes/base/secrets.example.yaml`
- Secret-manager wiring example: `deploy/kubernetes/examples/secret-manager-external-secrets.yaml`
- Migration job templates: `deploy/kubernetes/examples/migration-jobs.yaml`
- SLO alert examples: `deploy/kubernetes/examples/slo-alerts.yaml`
- Saved observability queries: `deploy/kubernetes/examples/observability-queries.md`
- Load/chaos release gate checklist: `deploy/kubernetes/examples/load-chaos-checks.md`
- Production data cutover runbook: `docs/production_cutover.md`
- Production cutover rehearsal manifest: `deploy/kubernetes/examples/production-cutover-manifest.example.json`
- Disaster recovery runbook: `docs/disaster_recovery.md`
- Disaster recovery rehearsal manifest: `deploy/kubernetes/examples/disaster-recovery-manifest.example.json`

Rollout order:

1. Apply datastore migrations per service.
2. Deploy shared infrastructure: event bus, secret/cert volumes, observability collector.
3. Deploy backend gRPC services.
4. Deploy API Gateway last.
5. Run smoke tests against `/health`, `/openapi.json`, one authenticated customer flow, one
   document/inventory flow, and async consumer lag/DLQ gates.

Rollback rule: rollback gateway first, then downstream services in reverse rollout order.

## Database Migrations

Current services still use local/dev table bootstrap. Production rollout must use one
migration stream per service-owned datastore:

| Service | Migration owner |
| --- | --- |
| identity-service | users/auth schema |
| customer-service | customers/purchases schema |
| product-service | product catalog schema |
| warehouse-service | warehouse/position schema |
| inventory-service | inventory stock schema |
| documents-service | documents/document_items schema |
| audit-service | audit_events schema |
| reporting-service | read-model/reporting schema |
| ai-service | vector/index metadata schema |

Kubernetes migration jobs call each service-owned `*-migrate` command before runtime startup.
Runtime table bootstrap is local/dev only and is enabled in root compose through
`LOCAL_DB_BOOTSTRAP_ENABLED=1`; production deployment must keep that variable unset or false.

## Production Data Cutover

Use `docs/production_cutover.md` and
`deploy/kubernetes/examples/production-cutover-manifest.example.json` before shifting real data to
the service-owned datastores. The rehearsal must capture source/target database snapshots, Redis
event offsets, release image tags, reconciliation output, and rollback notes.

Baseline rehearsal command:

```bash
python3 scripts/cutover_rehearsal.py \
  --manifest deploy/kubernetes/examples/production-cutover-manifest.example.json \
  --dry-run
```

## Runbooks

Incident triage:

1. Check API Gateway `/health`, `/metrics`, `x-request-id`, and `traceparent`.
2. Identify failed downstream service from 503/504 responses and gateway logs.
3. Check gRPC service healthcheck status.
4. Check Redis stream length and audit consumer logs.
5. Roll back the most recent changed service if errors correlate with deployment.

Replay events:

1. Pause the affected consumer.
2. Capture the replay stream id range.
3. Re-run the consumer from the selected `AUDIT_EVENT_CONSUMER_START_ID`.
4. Confirm idempotency with `event_id` in audit payload.

DLQ drain:

1. Fix or roll back the failing consumer handler.
2. Run `scripts/drain_dlq.py --dry-run` against the service-owned DLQ stream.
3. Drain into `wms.events.replay`.
4. Confirm duplicate `event_id` handling before resuming normal consumer reads.

AI reindex:

1. Enable the `ai` profile only for the reindex window.
2. Rebuild/reload vector data from the service-owned document/product sources.
3. Disable the profile again if AI is not part of normal dev/test.

Disaster recovery:

1. Follow `docs/disaster_recovery.md` to restore service-owned datastore snapshots.
2. Restore Redis stream snapshots and record `wms.events`, `wms.events.replay`, and DLQ offsets.
3. Run `scripts/dr_rehearsal.py --dry-run` against the DR manifest before opening traffic.
4. Validate auth, document idempotency, inventory totals, and reporting projection rebuild.

## API And Proto Versioning

- REST remains under `/api/v1`.
- Proto packages remain under `wms.<domain>.v1`.
- Additive fields are safe; never renumber or reuse proto field numbers.
- Removing REST fields or proto fields requires a new version and a migration window.
- Gateway OpenAPI and proto contract tests must pass before release.
