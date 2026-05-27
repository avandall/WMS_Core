# Internal Architecture Refactor Plan

This plan starts from the current `gRPC` branch where the active runtime is already
gRPC-first microservices. The legacy `Services/wms-monolith` tree is out of scope for this
plan. The next goal is to optimize the internal architecture of each active service around
its real WMS ownership without forcing heavy DDD everywhere.

## Current Baseline

- Runtime services exist for gateway, identity, customer, product, warehouse, inventory,
  documents, audit, reporting, and AI.
- The monolith is no longer part of the active architecture. Do not spend refactor effort on
  `Services/wms-monolith` unless a future migration/reference task explicitly asks for it.
- Root compose gives each runtime service a service-owned datastore connection.
- Redis Streams exists as the async event bus with durable consumer groups, DLQ streams, and
  replay support.
- `proto/wms/*/v1` is the transport contract source; generated `*_pb2.py` files are build
  artifacts and should not become architecture boundaries.
- Phase B removed the known non-owned internal modules from active services. Future non-owned
  module additions should fail the ownership guardrail tests before they become part of the
  runtime baseline.
- `docs/data_ownership.md` and `docs/events.md` are the current ownership/event baselines
  that this plan must keep consistent.

Phase B completed service ownership cleanup:

- `identity-service`: kept users and removed the non-owned positions module.
- `product-service`: kept products and removed inventory module/table ownership.
- `customer-service`: kept customers and removed unused shared reporting orchestration.
- `audit-service`: kept audit and removed unused shared reporting orchestration.
- `inventory-service`: kept inventory, moved warehouse stock rows to inventory-owned models,
  and removed product/warehouse module ownership.
- `warehouse-service`: kept warehouses/positions and removed document/product/inventory module
  ownership.
- `documents-service`: kept documents and removed audit/customer/inventory/position/product/user/
  warehouse module ownership.
- `reporting-service`: kept reporting read-model ledger and removed copied operational modules.

## Target Architecture

Use a mixed architecture instead of forcing one pattern everywhere:

| Service | Target pattern | Owned internals | Allowed external view |
| --- | --- | --- | --- |
| `api-gateway` | BFF/API composition | REST routes, auth, validation, request IDs, tracing, gRPC error mapping | gRPC clients and response composition only |
| `identity-service` | Lightweight Clean Architecture | users, auth/token policy, roles/permissions | identity lookup/auth APIs |
| `customer-service` | CRUD + application service | customer profile and purchase history ownership | customer query APIs/events |
| `product-service` | Catalog CRUD + light domain rules | products/SKUs/catalog lifecycle | product query APIs/events |
| `warehouse-service` | Tactical DDD where useful | warehouses, locations/bins, capacity/status metadata | warehouse/location APIs/events |
| `inventory-service` | Tactical DDD + use cases | stock, reservations, movement ledger, idempotency | product/warehouse references by ID only |
| `documents-service` | Tactical DDD + aggregate workflow | documents, document items, lifecycle state | product/customer/warehouse references by ID/snapshots only |
| `audit-service` | Event append/read service | audit event records | event envelopes consumed from Redis Streams |
| `reporting-service` | CQRS/read-model projections | projection tables and event idempotency ledger | operational snapshots from events only |
| `ai-service` | Pipeline/adapters | opt-in ingestion, retrieval, generation, provider adapters | projection snapshots/events only |

## Architecture Rules

- A service may write only its owned tables. Cross-service copies are read models or
  denormalized snapshots, never source-of-truth tables.
- `domain` must not import `application`, `infrastructure`, gRPC, FastAPI, SQLAlchemy sessions,
  Redis clients, or generated protobuf modules.
- `application` coordinates use cases and depends on ports/interfaces, not concrete
  repositories, transport DTOs, or other service databases.
- `infrastructure` implements repository, event-bus, database, search, and provider adapters.
- `grpc`/HTTP adapters translate transport DTOs to application commands/queries.
- API Gateway must not contain WMS business rules.
- Events are contracts. Additive event changes require schema versioning and contract tests;
  breaking changes require a new event type or versioned consumer path.
- Default dev/test/build flows must not build AI images, install heavy AI dependencies, or run AI
  tests unless the phase explicitly changes `ai-service`.
- Generated protobuf files may be regenerated, but hand edits belong in `proto/wms/*/v1`.

## Testing Policy

Each architecture refactor phase must finish with a verification set appropriate to the blast
radius:

- Unit tests for changed domain/application logic.
- Import-boundary and ownership contract tests for changed services.
- Event contract tests for producers, consumers, schema versioning, unknown fields, and replay.
- API Gateway contract tests when public REST/gRPC behavior or error mapping changes.
- E2E gateway stack tests when public REST/gRPC behavior, compose config, shared utilities, or
  event flow changes.
- `docker compose config --quiet` when compose changes.
- `kubectl kustomize deploy/kubernetes/base` and server dry-run when Kubernetes manifests
  change.
- `git diff --check` before commit.

Default test commands must avoid AI:

```bash
env UV_CACHE_DIR=/tmp/uv-cache uv run --group dev pytest -q tests/contract tests/e2e
tests/e2e/run_gateway_stack_tests.sh
```

AI-specific verification is opt-in only:

```bash
docker compose --profile ai build ai-service
docker compose --profile ai up -d ai-service
env UV_CACHE_DIR=/tmp/uv-cache uv run --package ai-service pytest -q Services/ai-service
```

If a shared change accidentally makes default tests build/install AI dependencies, fix the test
or compose boundary before continuing the phase.

## Commit Policy

Commit after each completed phase so the refactor has stable rollback points.

- Commit only after the phase acceptance checks and required tests pass.
- Clean generated cache artifacts such as `__pycache__` before committing.
- Use this message format:

```text
Phase <letter-or-number>: <short summary>
```

Examples:

```text
Phase A: add architecture boundary tests
Phase B: clean service module ownership
Phase C: refactor document lifecycle aggregate
```

## Phase A: Architecture Baseline and Guardrails

Status: DONE.

Goal: make the intended architecture explicit and testable before moving logic.

- Added `docs/architecture.md` with the target patterns, dependency rules, and module
  ownership map.
- Added `docs/service_template.md` with the expected folder shape per service category:
  BFF, CRUD service, DDD service, event consumer, read-model service, and AI pipeline.
- Added import-boundary contract tests per service category.
- Added ownership baseline tests that fail if active services add new non-owned modules or
  datastore tables before Phase B.
- Marked generated protobuf packages as allowed transport artifacts, not domain/application
  dependencies.

Acceptance:

- Contract tests fail if `domain` imports infrastructure or transport code.
- Contract tests fail if a service registers non-owned operational modules as owned tables.
- New contributors can identify the target pattern and owned internals for each service.

## Phase B: Service Ownership Cleanup

Status: DONE.

Goal: remove non-owned internal modules from active services before deeper domain refactors.

- Trim each service to its owned module set:
  - `documents-service`: DONE. Kept documents and replaced product/customer/warehouse/user/
    inventory ownership with stored IDs and event-driven follow-up work for Phase C.
  - `warehouse-service`: DONE. Kept warehouses/positions and removed
    document/product/inventory ownership code.
  - `inventory-service`: DONE. Kept inventory, removed product/warehouse modules, and kept
    warehouse stock rows as inventory-owned ID references.
  - `product-service`: DONE. Kept products and removed inventory module/table ownership.
  - `identity-service`: DONE. Kept users and removed the non-owned positions module.
  - `reporting-service`: DONE. Kept reporting projections/idempotency ledger and removed copied
    operational modules.
- Update DB initialization lists so services create only owned tables plus explicitly named read
  models.
- Keep compatibility with existing gRPC APIs while internals move.
- Add boundary tests that encode the final allowed module list for each service.

Acceptance:

- `find Services/*/src/app/modules -maxdepth 1` shows only owned modules or explicitly named
  read-model modules.
- Service startup still initializes required tables without cross-service source-of-truth tables.
- Gateway stack tests still pass through the existing REST/gRPC flows.

## Phase C: Documents Domain Refactor

Status: DONE.

Goal: make `documents-service` the owner of document lifecycle rules.

- Kept the `Document` aggregate as the lifecycle owner with `DRAFT`, `POSTED`, and `CANCELLED`
  states.
- Moved posting/cancellation rules and event publishing into application use cases.
- Kept references to customer/product/warehouse as IDs and document-line snapshots.
- Emits typed document events aligned with `docs/events.md`:
  - `DocumentUploaded`
  - `DocumentPosted`
  - `DocumentCancelled`
  - `InventoryMovementRequested`
- Posting is idempotent by document lifecycle and uses deterministic event IDs.
- gRPC payload mapping stays in the adapter; persistence commits happen in application use cases.

Acceptance:

- Posting the same document/event twice is idempotent.
- Invalid state transitions are rejected in domain/application tests.
- gRPC servicer contains transport mapping only.
- No product/customer/warehouse repository implementation is owned by `documents-service`.

## Phase D: Inventory Domain Refactor

Status: DONE.

Goal: make inventory consistency explicit.

- Added application use cases: `adjust_inventory`, `reserve_stock`, `release_reservation`, and
  `apply_document_movement`.
- Added value objects: `Quantity`, `Sku`, and `WarehouseLocation`.
- Added `inventory_movement_ledger` as the idempotency ledger for stock movements.
- `inventory-service` consumes `InventoryMovementRequested` and emits `InventoryMovementApplied`.
- Published inventory events are aligned with `docs/events.md`: `InventoryAdjusted`,
  `StockReserved`, `ReservationReleased`, and `InventoryMovementApplied`.
- Movement event replay is idempotent through deterministic source event IDs.

Acceptance:

- Stock movement tests cover positive, negative, duplicate, and rollback cases.
- Event consumers can replay inventory movement safely.
- Inventory references product and warehouse by ID/snapshot/API/event only.

## Phase E: Event Contract Hardening

Status: DONE.

Goal: make async integration safe across services before expanding projections.

- Defined event schemas in `docs/events.md` and `tests/fixtures/event_contracts.json`.
- Added fixtures for each published event type.
- Added contract tests that assert required envelope fields and service-owned payload fields.
- Added consumer hardening checks for unknown fields, duplicate `event_id`, replay metadata, and
  older schema versions.
- Documented the breaking-change policy and when to create a new event type.

Acceptance:

- Event schema changes require test updates.
- Consumers tolerate additive fields.
- Replay through `wms.events.replay` preserves idempotency behavior.

## Phase F: Reporting CQRS Refactor

Status: DONE.

Goal: turn `reporting-service` into a read-model service.

- Kept `reporting_read_model_events` as the event idempotency ledger.
- Added projection tables for existing/planned report queries:
  - `inventory_summary`
  - `document_summary`
  - `sales_summary`
  - `warehouse_activity_summary`
- Converted read-model ingestion into projection handlers for document and inventory events.
- Reporting gRPC queries read projection tables only.

Acceptance:

- Reports do not depend on operational repository implementations.
- Replay can rebuild projections from `wms.events` or `wms.events.replay`.
- Reporting DB contains projection/read-model tables, not copied source-of-truth modules.

## Phase G: Warehouse Domain Refactor

Status: DONE.

Goal: separate warehouse/location rules from generic CRUD.

- Modeled warehouse locations and bins as domain value objects: `WarehouseLocation`,
  `BinCode`, and `PositionType`.
- Kept capacity/status rules out until a concrete workflow needs persisted capacity state.
- Exposed application use cases for warehouse creation, location updates, location metadata
  lookup, and position lookup.
- Kept inventory quantities in `inventory-service`; warehouse owns structure/location metadata.

Acceptance:

- Warehouse service does not own inventory movement logic.
- Inventory service references warehouse by ID/location metadata through APIs/events only.

## Phase H: Lightweight CRUD Service Cleanup

Status: DONE.

Goal: simplify services that do not need heavy DDD.

Services:

- `customer-service`
- `product-service`
- `identity-service`

Actions completed:

- Kept application service + repository pattern for customer, product, and identity.
- Removed empty domain entity/exception folders that did not contain real rules.
- Kept meaningful domain rules in product and identity entities.
- Replaced product command/query handler layers with lightweight application DTOs.
- Kept identity auth/token policy in the application boundary, not domain.

Acceptance:

- CRUD service folders are smaller and easier to scan.
- No fake abstraction remains solely because the earlier code layout had it.

## Phase I: API Gateway BFF Cleanup

Status: DONE.

Goal: keep gateway as transport orchestration only.

- Kept auth, validation, rate limits, tracing, request IDs, and gRPC error mapping in gateway.
- Added a central gRPC call wrapper for retry/error mapping at the transport boundary.
- Moved response presentation into gateway presenters so route handlers stay orchestration-focused.
- Added contract tests that prevent gateway imports of service domain/application/infrastructure
  modules and WMS repositories.
- Kept OpenAPI routes stable for the existing REST/gRPC surface.

Acceptance:

- Gateway tests assert routing/error mapping.
- No inventory/document/customer business rules live in gateway.

## Phase J: AI Pipeline Cleanup

Status: DONE.

Goal: keep AI isolated and event-driven.

- Kept AI behind the opt-in compose/runtime profile.
- Kept AI outside default contract/E2E tests and default Docker builds.
- Kept a separate AI test command/profile for phases that explicitly touch AI.
- Split AI service internals into:
  - ingestion
  - indexing
  - retrieval
  - generation
  - provider adapters
- Wrapped the baseline JSONL reindex queue behind an AI-owned `ReindexJobStore` boundary so it
  can be replaced with a durable job table or queue when needed.
- Converted event envelopes/projection snapshots into replayable AI reindex jobs instead of
  reading operational service databases.

Acceptance:

- Dev/test stays fast without AI.
- AI reindex can be replayed from events or projection snapshots.

## Closed Gaps After Phase K Audit

The Phase K audit found work that was intentionally outside the first architecture cleanup pass.
Those gaps are now covered by Phase L-O:

- Phase L replaced migration placeholders and monolith seed dependencies with service-owned
  migration and fixture entrypoints.
- Phase M hardened event delivery, replay, and DLQ recovery.
- Phase N revalidated deployment, observability, and security boundaries.
- Phase O recorded the monolith archive policy and rollback reference.

The phases after O are not internal refactor phases. They are production-readiness phases for
real data cutover, automated release enforcement, operational recovery, and security governance.

## Phase K: Refactor Completion Audit

Status: DONE.

Goal: close the architecture refactor with one explicit, repeatable validation pass.

- Ran full default contract and E2E verification from the root compose stack through
  `tests/e2e/run_gateway_stack_tests.sh`.
- Validated gateway OpenAPI/proto contract coverage through the default contract suite.
- Rechecked service ownership docs against actual compose datastore URLs, initialized tables, and
  module folders.
- Verified event replay posture for audit, inventory, reporting, and AI consumers through
  documented replay commands and contract tests.
- Recorded the final phase commit list and rollback points in `docs/refactor_completion_audit.md`.

Acceptance:

- Default verification passes without AI build/start.
- `docs/data_ownership.md`, `docs/events.md`, and this plan agree with the current source.
- Any remaining intentional gaps are listed as Phase L-O work, not hidden in stale docs.

## Phase L: Production Migration and Fixture Ownership

Status: DONE.

Goal: replace local bootstrap assumptions with service-owned production migration paths.

- Added `*-migrate` commands for each datastore-owning service.
- Replaced Kubernetes migration-job placeholder commands with service-owned migration commands.
- Kept runtime table bootstrap local/dev only through `LOCAL_DB_BOOTSTRAP_ENABLED=1` in compose;
  production runtime manifests keep that variable unset.
- Added `*-fixtures` entrypoints so active seed/dev fixture ownership is service-owned instead of
  monolith-owned.
- Added contract tests that production config does not rely on local SQLite defaults or runtime
  table creation.

Acceptance:

- Every datastore-owning service has a migration command documented and wired into deployment
  examples.
- Production rollout can apply migrations before service startup.
- Monolith seed scripts are no longer required for active service dev/test flows.

## Phase M: Transactional Event Delivery Hardening

Status: DONE.

Goal: make async producer and consumer reliability symmetric.

- Added publish-after-commit guardrails for services that emit domain events.
- Kept consumer idempotency ledgers for inventory, reporting, audit, and AI reindex workflows.
- Added `scripts/drain_dlq.py` for DLQ drain/replay of failed event batches.
- Defined event ordering expectations per aggregate where ordering matters.
- Added contract tests for producer publish ordering, DLQ drain metadata, duplicate delivery, and
  replay posture.

Acceptance:

- No domain event is acknowledged as published before the owning transaction commits.
- Replaying an event range is idempotent across all active consumers.
- DLQ recovery is documented and tested at least at contract/integration level.

## Phase N: Deployment, Observability, and Security Hardening

Status: DONE.

Goal: make the refactored service boundaries deployable and operable.

- Revalidated Kubernetes manifests after the final service boundary changes.
- Added environment-specific secret-manager wiring example for `wms-secrets` and `wms-grpc-mtls`.
- Verified and documented mTLS/JWT/key-rotation paths for gateway-to-service traffic.
- Added saved PromQL queries for request rate, error rate, latency, Redis stream lag, DLQ depth,
  and consumer replay status.
- Expanded release smoke, load, and chaos checks to cover auth, customer flow,
  document/inventory flow, and async lag gates.
- Kept `ai-service` out of the default deployment unless an environment explicitly enables it.

Acceptance:

- `kubectl kustomize deploy/kubernetes/base` and server dry-run pass for the target cluster.
- Release gates cover health, auth, one core customer flow, one document/inventory flow, and
  async consumer lag.
- AI remains opt-in in both compose and deployment artifacts.

## Phase O: Monolith Archive Exit

Status: DONE.

Goal: decide whether the archived monolith can be frozen, moved, or deleted.

- Confirmed API Gateway parity for required business workflows through gateway contract and E2E
  gates.
- Confirmed service-owned migrations and fixtures have replaced monolith operational dependencies.
- Confirmed no active scripts, CI jobs, compose services, or deployment manifests import or execute
  monolith internals.
- Chose the archive policy: keep `Services/wms-monolith/` as frozen read-only reference until the
  next accepted tagged service release; delete it later in a dedicated commit if no rollback/parity
  investigation is open. Rollback reference tag: `phase-o-monolith-archive-exit`.
- Updated contributor docs so new work starts from services, gateway, proto, and deployment
  artifacts only.

Acceptance:

- The team has an explicit monolith archive/delete decision with a rollback reference tag.
- Active development workflows no longer mention monolith commands except historical reference.
- Contract tests continue to guard against monolith re-entry into active runtime paths.

## Phase P: Production Data Cutover and Backfill

Status: DONE.

Goal: prove the refactored services can take over real production data, not only local/dev data.

- Defined the source-to-target mapping for each owned datastore:
  - users/auth data to `identity-service`
  - customers to `customer-service`
  - products/SKUs to `product-service`
  - warehouses/positions/locations to `warehouse-service`
  - inventory balances and movement history to `inventory-service`
  - documents and document items to `documents-service`
  - audit history to `audit-service`
  - reporting projections to `reporting-service` rebuild/backfill
- Added `docs/production_cutover.md`, a manifest example, and `scripts/cutover_rehearsal.py` so
  dry-run cutover rehearsals can validate row counts, key mappings, foreign-ID references, and
  snapshot fields before writing target databases.
- Defined the cutover order, read-only window, rollback point, and post-cutover reconciliation
  checks.
- Added backfill/replay commands for reporting and AI read models without reading operational
  service databases directly.
- Recorded which data is migrated, rebuilt from events, manually seeded, or intentionally dropped
  in the production cutover runbook and rehearsal manifest.

Acceptance:

- A production-like cutover rehearsal can run against disposable target databases.
- Reconciliation output covers counts, orphan references, document totals, inventory totals, and
  reporting projection freshness.
- Rollback steps identify the exact database snapshots, event offsets, and release images needed
  to return to the previous runtime.

## Phase Q: CI/CD Release Enforcement

Status: DONE.

Goal: turn documented release gates into automated checks that block unsafe releases.

- Added CI jobs for Contract tests, gateway E2E smoke, compose config validation,
  kustomize render, production cutover dry-run, and generated proto drift.
- Added release build checks for all non-AI runtime images and kept AI image checks behind an
  explicit opt-in/profile.
- Added SBOM and vulnerability scan steps for release images.
- Enforced migration-job presence and service-owned datastore configuration through existing
  deployment and migration contract tests in the release gates.
- Added `scripts/release_artifact.py` and `docs/release_artifact.md` to publish release artifacts
  with the commit SHA, image tags, migration command list, and rollback
  notes.

Acceptance:

- Pull requests fail if architecture guardrails, compose config, proto generation, or kustomize
  validation drift.
- Release candidates fail if SBOM/image scan, migration checks, or smoke gates fail.
- The release artifact has enough information to redeploy or roll back without reading local
  developer notes.

## Phase R: Backup, Restore, and Disaster Recovery

Status: DONE.

Goal: make the service-owned datastore model recoverable under real failure scenarios.

- Defined backup ownership, retention, encryption, and restore order for each service datastore.
- Defined Redis Streams persistence, snapshot, and restore expectations for `wms.events`, replay
  streams, and DLQ streams.
- Added `docs/disaster_recovery.md`, a DR manifest example, and `scripts/dr_rehearsal.py` with
  restore rehearsal steps for identity, inventory, documents, reporting projections, and the
  event bus.
- Documented RPO/RTO targets by service and by business workflow.
- Added recovery checks that verify auth works, document posting is not duplicated, inventory totals
  reconcile, and reporting projections can be rebuilt.

Acceptance:

- A disposable environment can be restored from backups and replayed to a known event offset.
- Recovery runbooks include restore order, validation queries, event replay boundaries, and
  rollback/roll-forward choices.
- RPO/RTO targets are explicit enough for release and incident decisions.

## Phase S: Security Governance and Authorization Hardening

Status: TODO.

Goal: move from baseline security wiring to enforceable production security governance.

- Define fine-grained authorization scopes/permissions at the API Gateway boundary for WMS
  workflows.
- Add tests for admin-only actions, warehouse/inventory/document permissions, and token expiry or
  rotation behavior.
- Define secret rotation cadence for JWT signing keys, gRPC mTLS certificates, database
  credentials, and external provider keys.
- Add audit requirements for privileged operations, failed auth attempts, data export, and manual
  inventory adjustments.
- Add dependency/license scanning policy and remediation ownership for shared libraries and each
  service image.

Acceptance:

- Gateway authorization tests cover the main role/scope matrix without pushing authz rules into
  downstream domain services.
- Secret and certificate rotation has rehearsal steps and rollback instructions.
- Audit events provide enough detail to investigate privileged or destructive operations.

## Suggested Order

1. Phase A: Architecture Baseline and Guardrails
2. Phase B: Service Ownership Cleanup
3. Phase C: Documents Domain Refactor
4. Phase D: Inventory Domain Refactor
5. Phase E: Event Contract Hardening
6. Phase F: Reporting CQRS Refactor
7. Phase G: Warehouse Domain Refactor
8. Phase H: Lightweight CRUD Service Cleanup
9. Phase I: API Gateway BFF Cleanup
10. Phase J: AI Pipeline Cleanup
11. Phase K: Refactor Completion Audit
12. Phase L: Production Migration and Fixture Ownership
13. Phase M: Transactional Event Delivery Hardening
14. Phase N: Deployment, Observability, and Security Hardening
15. Phase O: Monolith Archive Exit

16. Phase P: Production Data Cutover and Backfill
17. Phase Q: CI/CD Release Enforcement
18. Phase R: Backup, Restore, and Disaster Recovery
19. Phase S: Security Governance and Authorization Hardening

## Non-Goals

- Do not rewrite every service into heavy DDD.
- Do not merge service databases.
- Do not make AI part of default dev/test.
- Do not move business logic into API Gateway for convenience.
- Do not hand-edit generated protobuf Python files.
- Do not introduce a service mesh before service boundaries are stable.
