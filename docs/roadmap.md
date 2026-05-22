# Roadmap (Long-term)

Roadmap dựa trên `MICROSERVICES_REFACTOR_PLAN.md`, nhưng cập nhật theo trạng thái hiện tại (gRPC-first).

## Status

- Phase 0: Preparation — DONE
- Phase 1: Identity Service — DONE (Identity gRPC + token validation)
- Phase 2: Customer/Product/Warehouse — DONE (gRPC services + API Gateway REST→gRPC)
- Phase 3: Inventory + Documents — DONE (gRPC services + API Gateway REST→gRPC + event hooks placeholder)
- Phase 4: Audit + Reporting — DONE (gRPC services + API Gateway REST→gRPC)
- Phase 5: AI Service — DONE (gRPC service + API Gateway REST→gRPC)
- Phase 6: Harden API Gateway (Core) — DONE
- Phase 7: Observability & Reliability — DONE
- Phase 8: Docker/Compose “Run For Real” — DONE
- Phase 9: CI + Contract/E2E Migration — DONE (gateway contract/E2E smoke on root compose; AI opt-in)
- Phase 10: Data Ownership & Datastores — DONE (per-service local datastore baseline + ownership guards)
- Phase 11: Event Bus & Async Workflows — DONE (Redis Streams baseline + audit consumer)
- Phase 12: Production Observability (OpenTelemetry) — DONE (W3C trace context + OTLP-ready baseline)
- Phase 13: Security Hardening (Prod) — DONE (gateway hardening + opt-in gRPC mTLS baseline)
- Phase 14: Resilience & SLO Readiness — DONE (SLO baseline + circuit breaker + event backpressure)
- Phase 15: Release/Deployment & Ops — DONE (release contract + ops runbooks + CI cleanup)
- Phase 16: Monolith Retirement & Codebase Simplification — DONE (monolith archived outside active workspace/CI)
- Phase 17: Production Deployment Automation — TODO
- Phase 18: Advanced Async/Analytics Workflows — TODO

## Phase 6: Harden API Gateway (Core)

Goal: gateway là public REST entrypoint và enforce policy đúng chuẩn.

- Replace ad-hoc REST payload dicts with Pydantic DTOs trong `Services/api-gateway/`
- Centralize authz/permissions trong gateway (không chỉ authn)
- Consistent error mapping (gRPC→HTTP) + validation
- Rate limiting/caching policy (hiện rate limit là dev-only, cần chuẩn hoá)

## Phase 7: Observability & Reliability

Goal: debug/trace cross-service calls dễ dàng và ổn định.

- Structured logs (JSON) tại gateway + services
- Propagate `x-request-id` qua gRPC metadata ở mọi gRPC call (gateway→services, services→services)
- Metrics surface (Prometheus-ready) cho gateway + services
- gRPC deadlines/timeouts policy + retry policy where safe

## Phase 8: Docker/Compose “Run For Real”

Goal: `docker compose up` chạy được toàn stack (không placeholder `sleep infinity`).

- Add `Dockerfile` per service (hoặc shared base image)
- Update root `docker-compose.yml` để run:
  - API Gateway (uvicorn)
  - mỗi service gRPC server (và REST server chỉ khi cần)
- Add healthchecks cho tất cả containers

## Phase 9: CI + Contract/E2E Migration

Goal: CI test theo entrypoint mới (API Gateway) thay vì monolith.

- DONE: Add contract/e2e tests against API Gateway + gRPC stack
- DONE: Migrate GitHub Actions integration/contract tests từ `Services/wms-monolith` sang root stack
- DONE: Keep `Services/wms-monolith/tests/refactor_guard` as temporary safety net until Phase 16 retirement
- CI/E2E uses the root `docker-compose.yml` and selects only the services needed for the gateway smoke path (`api-gateway`, `identity-service`, `customer-service`).
- Gateway E2E runs under an isolated Compose project (`wms-gateway-e2e`) so cleanup does not stop a developer's normal root stack.
- Root compose keeps `ai-service` behind the `ai` profile, so default dev/test commands do not build or start it.
- Full-stack compose validation including `ai-service` is intentionally left as an explicit/manual run: `docker compose --profile ai up -d`.
- Phase 16 removed monolith guard jobs from default CI after gateway contract/E2E became the active safety net.

## Phase 10: Data Ownership & Datastores

Goal: đúng “microservice chuẩn” về data autonomy (không share DB schema/joins).

- DONE: Root compose assigns a distinct local datastore connection per service instead of one inherited shared `DATABASE_URL`.
- DONE: Document current table ownership/read-model boundaries in `docs/data_ownership.md`.
- DONE: Decide per-service datastore strategy:
  - Separate DB per service (selected for local/dev baseline)
- DONE: Move each service to its own DB connection:
  - Local compose DB connection isolation: `identity-service`, `customer-service`, `product-service`, `warehouse-service`, `inventory-service`,
    `documents-service`, `audit-service`, `reporting-service`, `ai-service`
  - Runtime `create_all` remains local/dev bootstrap only; production migration rollout belongs to release/ops hardening.
- DONE: Remove the blocking cross-service FKs from `audit-service` so it owns and initializes `audit_events` in its own datastore.
- DONE: Define data duplication boundaries (read models) for reporting/search in `docs/data_ownership.md`.
- DONE: Add contract guards for compose datastore isolation and audit-service data boundaries.
- Deferred: seed/dev fixtures are optional and should follow service-specific migrations/fixtures when needed.

## Phase 11: Event Bus & Async Workflows

Goal: thay placeholder events bằng message broker thật + consumer pipelines.

- DONE: Choose broker (Redis Streams) + local docker-compose support via `event-bus`
- DONE: Define event contracts + versioning in `docs/events.md`:
  - `DocumentUploaded`, `DocumentPosted`, `InventoryAdjusted`, `ProductUpdated`, `WarehouseCreated`, ...
- DONE: Implement Redis-backed publishers in shared utils with stdout fallback
- DONE: Publish domain events from product/document/warehouse/inventory gRPC services
- DONE: Implement first consumer pipeline:
  - `audit-service` ingests cross-service events into `audit_events`
- DONE: Add event envelope `event_id` idempotency key
- Deferred: durable consumer groups, retry/dead-letter queues, reporting read-model consumers, and AI reindex consumers

## Phase 12: Production Observability (OpenTelemetry)

Goal: trace + metrics + logs thống nhất end-to-end.

- DONE: Adopt W3C `traceparent` propagation baseline for:
  - API Gateway HTTP middleware
  - API Gateway gRPC client metadata
  - gRPC server interceptors
- DONE: Keep `x-request-id` as human-friendly correlation id.
- DONE: Add structured JSON logs with `trace_id`/`span_id`.
- DONE: Keep Prometheus-style metrics endpoints for gateway/services.
- DONE: Add OTLP-ready compose env (`OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_TRACES_EXPORTER`).
- Deferred: install/export with the full OpenTelemetry SDK and collector dashboards during deployment/ops hardening.

## Phase 13: Security Hardening (Prod)

Goal: production-grade security posture.

- Internal traffic security:
  - DONE: Add opt-in mTLS support for gRPC servers and clients via env (`GRPC_TLS_ENABLED`, `GRPC_CLIENT_TLS_ENABLED`)
  - Network policies / service mesh (optional)
- AuthN/AuthZ:
  - Centralize authz policy in gateway (fine-grained scopes/roles)
  - Consider token introspection + key rotation strategy (JWKS or shared signing strategy)
- Secrets management:
  - DONE: Move compose `SECRET_KEY` to env interpolation with a local-dev default
  - Production must use Vault/Cloud secrets manager (no `.env` secrets committed)
- Request hardening:
  - DONE: Replace wildcard credentialed CORS with explicit env-configured origins
  - DONE: Add gateway security headers and request body limit
  - DONE: Scope rate limit by route and authorization token hash/IP
- Auditability:
  - DONE: Keep `x-request-id` and `traceparent` on gateway responses and downstream gRPC metadata
- Deferred: certificate rotation, service mesh/network policies, JWKS/key rotation, and full privileged-action audit policy belong to deployment/ops hardening.

## Phase 14: Resilience & SLO Readiness

Goal: behavior ổn định dưới failure/latency, đáp ứng SLO.

- DONE: Define initial SLOs (availability/latency) per endpoint class in `docs/resilience.md`
- Implement resilience patterns:
  - DONE: Keep env-configured gRPC timeouts/deadlines and bounded retries with backoff for idempotent calls
  - DONE: Add gateway circuit breaker for idempotent downstream gRPC calls
- Load testing:
  - Document critical workflow targets; full load tooling deferred to Phase 17 deployment automation
- Chaos/failure testing:
  - DONE: Document downstream-kill manual check and verify gateway E2E still returns bounded responses
- DONE: Add backpressure strategy for audit event consumer batch reads and stream length guard
- Deferred: distributed circuit state, bulkheads, durable DLQ/replay, and full automated load/chaos suites.

## Phase 15: Release/Deployment & Ops

Goal: shipable, maintainable, operable in production.

- DONE: Document container image tagging strategy and SBOM expectations in `docs/release_ops.md`
- Deployment:
  - DONE: Define deployment contract, rollout order, smoke checks, and rollback order
  - Kubernetes manifests/Helm are deferred to the deployment automation phase
- DONE: Define DB migration ownership per service and production rule: do not rely on `create_all`
- Runbooks:
  - DONE: Add incident triage, rollback, AI reindex, and event replay runbooks
- Versioning policy:
  - DONE: Document REST `/api/v1` and proto `wms.<domain>.v1` compatibility rules
- DONE: Remove stale root `python-ci.yml` workflow and make gateway E2E prefer `uv` workspace execution

## Phase 16: Monolith Retirement & Codebase Simplification

Goal: giảm technical debt sau khi microservice path đã chạy ổn.

- DONE: Remove `Services/wms-monolith` from root `uv` workspace membership.
- DONE: Remove monolith unit/refactor-guard jobs from default CI; gateway contract/E2E is the active CI path.
- DONE: Stop generating gRPC stubs into monolith with `scripts/gen_protos.py`.
- DONE: Keep `Services/wms-monolith` as archived reference only and document retirement criteria in `docs/monolith_retirement.md`.
- DONE: Document service-owned fixture targets and contributor entrypoints.
- DONE: Update root README/run docs so new contributors start from API Gateway + gRPC stack.
- Deferred to Phase 17/18: production migration jobs, read-model consumers, and final delete/archive sign-off after parity acceptance.

## Phase 17: Production Deployment Automation

Goal: biến release contract thành deployment artifact thật.

- Add Kubernetes manifests/Helm or equivalent deployment package
- Wire secret manager and gRPC cert rotation into deployment
- Add per-service migration commands/jobs
- Add OpenTelemetry collector/dashboard deployment
- Add automated load/chaos checks and SLO alerts

## Phase 18: Advanced Async/Analytics Workflows

Goal: hoàn thiện các workflow async/read-model còn deferred.

- Durable Redis consumer groups with retry/dead-letter queues
- Reporting read-model consumers
- AI reindex/replay consumer pipeline
- Event replay tooling and idempotency verification
- Cross-service analytics/search read-model hardening
