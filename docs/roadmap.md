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
- Phase 9: CI + Contract/E2E Migration — DONE (gateway contract/E2E smoke on minimal gRPC stack; AI opt-in)
- Phase 10: Data Ownership & Datastores — TODO
- Phase 11: Event Bus & Async Workflows — TODO
- Phase 12: Production Observability (OpenTelemetry) — TODO
- Phase 13: Security Hardening (Prod) — TODO
- Phase 14: Resilience & SLO Readiness — TODO
- Phase 15: Release/Deployment & Ops — TODO

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
- DONE: Keep `Services/wms-monolith/tests/refactor_guard` làm safety net cho đến khi retire monolith hoàn toàn
- CI/E2E uses `docker-compose.phase9.yml` as a minimal stack (`api-gateway`, `identity-service`, `customer-service`) to verify REST→gRPC without building the heavy AI image.
- Root compose keeps `ai-service` behind the `ai` profile, so default dev/test commands do not build or start it.
- Full-stack compose validation including `ai-service` is intentionally left as an explicit/manual run: `docker compose --profile ai up -d`.

## Phase 10: Data Ownership & Datastores

Goal: đúng “microservice chuẩn” về data autonomy (không share DB schema/joins).

- Decide per-service datastore strategy:
  - Separate DB per service (recommended) hoặc separate schema + strict access boundary
- Move each service to its own DB connection + migrations:
  - `identity-service`, `customer-service`, `product-service`, `warehouse-service`, `inventory-service`,
    `documents-service`, `audit-service`, `reporting-service`, `ai-service`
- Remove cross-domain DB reads/writes inside a service (no hidden coupling)
- Define data duplication boundaries (read models) for reporting/search
- Add seed/dev fixtures per service (optional)

## Phase 11: Event Bus & Async Workflows

Goal: thay placeholder events bằng message broker thật + consumer pipelines.

- Choose broker (NATS/Kafka/RabbitMQ/Redis Streams) + local docker-compose support
- Define event contracts + versioning:
  - `DocumentUploaded`, `InventoryAdjusted`, `ProductUpdated`, `WarehouseCreated`, `AuditEventLogged`, ...
- Implement publishers in domain services (outbox pattern recommended)
- Implement consumers:
  - `reporting-service` builds read models
  - `audit-service` ingests cross-service actions
  - `ai-service` reindex/update embeddings when documents/products change
- Add idempotency keys + retry/dead-letter strategy

## Phase 12: Production Observability (OpenTelemetry)

Goal: trace + metrics + logs thống nhất end-to-end.

- Adopt OpenTelemetry SDK for:
  - API Gateway (FastAPI)
  - gRPC clients/servers
- Trace propagation:
  - Use W3C `traceparent` or service-mesh propagation
  - Keep `x-request-id` as human-friendly correlation id
- Metrics:
  - Standardize Prometheus metrics naming/labels
  - Dashboards + alerts (latency, error rate, saturation)
- Logging:
  - Structured JSON logs with trace/span IDs

## Phase 13: Security Hardening (Prod)

Goal: production-grade security posture.

- Internal traffic security:
  - mTLS for gRPC (service-to-service)
  - Network policies / service mesh (optional)
- AuthN/AuthZ:
  - Centralize authz policy in gateway (fine-grained scopes/roles)
  - Consider token introspection + key rotation strategy (JWKS or shared signing strategy)
- Secrets management:
  - Use Vault/Cloud secrets manager (no `.env` secrets committed)
- Request hardening:
  - Input validation everywhere (DTOs)
  - Rate limit policy (per route/user), abuse prevention
- Auditability:
  - Ensure all privileged actions are auditable with request-id correlation

## Phase 14: Resilience & SLO Readiness

Goal: behavior ổn định dưới failure/latency, đáp ứng SLO.

- Define SLOs (availability/latency) per endpoint
- Implement resilience patterns:
  - timeouts/deadlines (already started), retries w/ backoff where safe
  - circuit breaker / bulkhead (optional)
- Load testing:
  - API Gateway throughput, critical workflows
- Chaos/failure testing:
  - kill a downstream service, verify graceful degradation
- Backpressure strategy for event consumers

## Phase 15: Release/Deployment & Ops

Goal: shipable, maintainable, operable in production.

- Container images + tagging strategy + SBOM
- Deployment:
  - Kubernetes manifests/Helm (or equivalent)
  - rolling updates + canary (optional)
- DB migration automation per service
- Runbooks:
  - incident response, rollback, reindex AI, replay events
- Versioning policy:
  - REST API versions in gateway
  - proto backward compatibility guidelines
