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

Goal: make `documents-service` the owner of document lifecycle rules.

- Introduce a `Document` aggregate with states: `draft`, `posted`, `cancelled`.
- Move posting/cancellation rules out of gRPC servicer into application use cases.
- Keep references to customer/product/warehouse as IDs and immutable document-line snapshots.
- Emit typed domain events aligned with `docs/events.md`; introduce new names only with event
  contract tests and migration notes:
  - current: `DocumentUploaded`, `DocumentPosted`
  - target additions when implemented: `DocumentCancelled`, `InventoryMovementRequested`
- Add idempotency key handling for posting.
- Keep gRPC payload mapping in the adapter layer only.

Acceptance:

- Posting the same document/event twice is idempotent.
- Invalid state transitions are rejected in domain/application tests.
- gRPC servicer contains transport mapping only.
- No product/customer/warehouse repository implementation is owned by `documents-service`.

## Phase D: Inventory Domain Refactor

Goal: make inventory consistency explicit.

- Add use cases:
  - `AdjustInventory`
  - `ReserveStock`
  - `ReleaseReservation`
  - `ApplyDocumentMovement`
- Add value objects:
  - `Quantity`
  - `Sku`
  - `WarehouseLocation`
- Add or formalize a movement ledger table/model if not already covered by the current schema.
- Publish typed events aligned with `docs/events.md`; introduce new names only with event
  contract tests and migration notes:
  - current: `InventoryAdjusted`, inventory read/list events
  - target additions when implemented: `StockReserved`, `ReservationReleased`,
    `InventoryMovementApplied`
- Enforce idempotency on movement events.

Acceptance:

- Stock movement tests cover positive, negative, duplicate, and rollback cases.
- Event consumers can replay inventory movement safely.
- Inventory references product and warehouse by ID/snapshot/API/event only.

## Phase E: Event Contract Hardening

Goal: make async integration safe across services before expanding projections.

- Define event schemas in docs and tests for the current event set in `docs/events.md`.
- Add fixtures for each published event type.
- Add producer tests that assert required envelope fields and service-owned payload fields.
- Add consumer tests for unknown fields, duplicate `event_id`, replay metadata, and older schema
  versions.
- Document the breaking-change policy and when to create a new event type.

Acceptance:

- Event schema changes require test updates.
- Consumers tolerate additive fields.
- Replay through `wms.events.replay` preserves idempotency behavior.

## Phase F: Reporting CQRS Refactor

Goal: turn `reporting-service` into a read-model service.

- Stop expanding non-owned operational modules inside reporting.
- Keep `reporting_read_model_events` as the idempotency ledger.
- Create projection tables only for reporting queries that exist or are planned:
  - `inventory_summary`
  - `document_summary`
  - `sales_summary`
  - `warehouse_activity_summary`
- Convert Redis consumers into projection handlers.
- Queries read projection tables only.

Acceptance:

- Reports do not depend on operational repository implementations.
- Replay can rebuild projections from `wms.events` or `wms.events.replay`.
- Reporting DB contains projection/read-model tables, not copied source-of-truth modules.

## Phase G: Warehouse Domain Refactor

Goal: separate warehouse/location rules from generic CRUD.

- Model warehouse locations/bins as domain concepts.
- Add capacity/status rules only if the current workflow needs them.
- Expose application use cases for warehouse creation, location updates, and lookup.
- Keep inventory quantities in `inventory-service`; warehouse owns structure/location metadata.

Acceptance:

- Warehouse service does not own inventory movement logic.
- Inventory service references warehouse by ID/location metadata through APIs/events only.

## Phase H: Lightweight CRUD Service Cleanup

Goal: simplify services that do not need heavy DDD.

Services:

- `customer-service`
- `product-service`
- `identity-service`

Actions:

- Keep application service + repository pattern.
- Remove empty domain folders if they do not contain real rules.
- Keep domain rules only where meaningful, such as SKU uniqueness or auth token policy.
- Standardize command/query DTOs.
- Keep authz/identity clients in adapter/application boundaries, not domain.

Acceptance:

- CRUD service folders are smaller and easier to scan.
- No fake abstraction remains solely because the earlier code layout had it.

## Phase I: API Gateway BFF Cleanup

Goal: keep gateway as transport orchestration only.

- Keep auth, validation, rate limits, tracing, request IDs, and gRPC error mapping.
- Move any WMS business decision into the owning service.
- Keep response composition explicit and covered by contract tests.
- Keep OpenAPI contract tests aligned with gateway routes after any endpoint movement.

Acceptance:

- Gateway tests assert routing/error mapping.
- No inventory/document/customer business rules live in gateway.

## Phase J: AI Pipeline Cleanup

Goal: keep AI isolated and event-driven.

- Keep AI behind the opt-in compose/runtime profile.
- Keep AI outside default contract/E2E tests and default Docker builds.
- Add a separate AI test command/profile for phases that explicitly touch AI.
- Split AI internals into:
  - ingestion
  - indexing
  - retrieval
  - generation
  - provider adapters
- Replace the baseline JSONL reindex queue with a durable job table or queue when needed.
- Consume read-model snapshots/events, not operational service databases.

Acceptance:

- Dev/test stays fast without AI.
- AI reindex can be replayed from events or projection snapshots.

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

## Non-Goals

- Do not rewrite every service into heavy DDD.
- Do not merge service databases.
- Do not make AI part of default dev/test.
- Do not move business logic into API Gateway for convenience.
- Do not hand-edit generated protobuf Python files.
- Do not introduce a service mesh before service boundaries are stable.
