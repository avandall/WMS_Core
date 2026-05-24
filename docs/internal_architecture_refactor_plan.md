# Internal Architecture Refactor Plan

This plan starts after the gRPC microservice extraction is complete. The current stack is
gRPC-first microservices with a pragmatic Clean Architecture/DDD-lite structure inherited
from the monolith. The next goal is to optimize each service around its real WMS role.

## Target Architecture

Use a mixed architecture instead of forcing one pattern everywhere:

| Service | Target pattern | Reason |
| --- | --- | --- |
| `api-gateway` | BFF/API composition | Public REST entrypoint, auth, request validation, gRPC error mapping |
| `identity-service` | Lightweight Clean Architecture | Auth/user/token logic, few domain aggregates |
| `customer-service` | CRUD + application service | Mostly customer profile and purchase history operations |
| `product-service` | Catalog CRUD + light domain rules | Product/SKU catalog, validation, lifecycle rules |
| `warehouse-service` | Tactical DDD | Warehouse/location/bin rules are WMS core concepts |
| `inventory-service` | Tactical DDD + use cases | Stock movement, reservations, idempotency, consistency rules |
| `documents-service` | Tactical DDD + aggregate workflow | Draft/post/cancel document lifecycle drives inventory changes |
| `audit-service` | Event append/read service | Durable event ingestion and audit query surface |
| `reporting-service` | CQRS/read-model projections | Analytics should read projections, not copy operational models |
| `ai-service` | Pipeline/adapters | Reindex, retrieval, generation, model/provider adapters |

## Architecture Rules

- `domain` must not import `application`, `infrastructure`, gRPC, FastAPI, SQLAlchemy sessions, or Redis clients.
- `application` coordinates use cases and depends on ports/interfaces, not concrete repositories.
- `infrastructure` implements repository/event-bus/search adapters.
- `grpc`/HTTP adapters translate transport DTOs to application commands/queries.
- Service-owned data remains mandatory; no cross-service database joins.
- Events are contracts. Additive event changes require schema versioning and contract tests.
- API Gateway must not contain WMS business rules.
- Every refactor phase must include focused tests for changed logic and a regression run that
  proves the API Gateway/gRPC flow still works.
- AI must remain outside default dev/test flows. Do not run AI tests, build AI images, or install
  heavy AI dependencies unless the phase explicitly changes `ai-service`.

## Testing Policy

Each architecture refactor phase must finish with a verification set appropriate to the blast
radius:

- Unit tests for changed domain/application logic.
- Contract tests for boundaries, events, API Gateway behavior, and service ownership rules.
- E2E gateway stack tests when public REST/gRPC behavior, compose config, shared utilities, or
  event flow changes.
- `docker compose config --quiet` when compose changes.
- `kubectl kustomize deploy/kubernetes/base` and server dry-run when Kubernetes manifests change.
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
Phase B: refactor document lifecycle aggregate
Phase C: harden inventory movement use cases
```

## Phase A: Architecture Baseline

Goal: make the intended architecture explicit and testable.

- Add `docs/architecture.md` with the target patterns and dependency rules.
- Add import-boundary contract tests per service category.
- Add a service template reference under `docs/service_template.md`.
- Mark which existing modules are legacy carry-over versus target structure.

Acceptance:

- Contract tests fail if `domain` imports infrastructure or transport code.
- New contributors can identify the target pattern for each service.

## Phase B: Documents Domain Refactor

Goal: make `documents-service` the owner of document lifecycle rules.

- Introduce `Document` aggregate with states: `draft`, `posted`, `cancelled`.
- Move posting/cancellation rules out of gRPC servicer into application use cases.
- Emit typed domain events:
  - `DocumentCreated`
  - `DocumentPosted`
  - `DocumentCancelled`
  - `InventoryMovementRequested`
- Add idempotency key handling for posting.
- Keep gRPC payload mapping in adapter layer only.

Acceptance:

- Posting the same document/event twice is idempotent.
- Invalid state transitions are rejected in domain/application tests.
- gRPC servicer contains transport mapping only.

## Phase C: Inventory Domain Refactor

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
- Add movement ledger table/model if not already covered by current schema.
- Publish typed events:
  - `InventoryAdjusted`
  - `StockReserved`
  - `ReservationReleased`
  - `InventoryMovementApplied`
- Enforce idempotency on movement events.

Acceptance:

- Stock movement tests cover positive, negative, duplicate, and rollback cases.
- Event consumers can replay inventory movement safely.

## Phase D: Warehouse Domain Refactor

Goal: separate warehouse/location rules from generic CRUD.

- Model warehouse locations/bins as domain concepts.
- Add capacity/status rules only if the current workflow needs them.
- Expose application use cases for warehouse creation, location updates, and lookup.
- Keep inventory quantities in `inventory-service`; warehouse owns structure/location metadata.

Acceptance:

- Warehouse service does not own inventory movement logic.
- Inventory service references warehouse by id/location metadata through APIs/events only.

## Phase E: Reporting CQRS Refactor

Goal: turn `reporting-service` into a read-model service.

- Stop expanding copied operational modules inside reporting.
- Create projection tables:
  - `inventory_summary`
  - `document_summary`
  - `sales_summary`
  - `warehouse_activity_summary`
- Convert Redis consumers into projection handlers.
- Queries read projection tables only.
- Keep `reporting_read_model_events` as the idempotency ledger.

Acceptance:

- Reports do not depend on operational repository implementations.
- Replay can rebuild projections from `wms.events` or `wms.events.replay`.

## Phase F: Event Contract Hardening

Goal: make async integration safe across services.

- Define event schemas in docs and tests.
- Add event contract fixtures for each published event type.
- Add producer tests that assert required fields.
- Add consumer tests for unknown fields and older schema versions.
- Document breaking-change policy.

Acceptance:

- Event schema changes require test updates.
- Consumers tolerate additive fields.

## Phase G: Lightweight CRUD Service Cleanup

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

Acceptance:

- CRUD service folders are smaller and easier to scan.
- No fake abstraction remains solely because the monolith had it.

## Phase H: API Gateway BFF Cleanup

Goal: keep gateway as transport orchestration only.

- Keep auth, validation, rate limits, tracing, request ids, and gRPC error mapping.
- Move any WMS business decision into owning service.
- Keep response composition explicit and covered by contract tests.

Acceptance:

- Gateway tests assert routing/error mapping.
- No inventory/document/customer business rules live in gateway.

## Phase I: AI Pipeline Cleanup

Goal: keep AI isolated and event-driven.

- Keep AI behind opt-in runtime profile.
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

1. Phase A: Architecture Baseline
2. Phase B: Documents Domain Refactor
3. Phase C: Inventory Domain Refactor
4. Phase F: Event Contract Hardening
5. Phase E: Reporting CQRS Refactor
6. Phase D: Warehouse Domain Refactor
7. Phase G: Lightweight CRUD Service Cleanup
8. Phase H: API Gateway BFF Cleanup
9. Phase I: AI Pipeline Cleanup

## Non-Goals

- Do not rewrite every service into heavy DDD.
- Do not merge service databases.
- Do not make AI part of default dev/test.
- Do not move business logic into API Gateway for convenience.
- Do not introduce a service mesh before service boundaries are stable.
