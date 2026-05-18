# Roadmap (Long-term)

Roadmap dựa trên `MICROSERVICES_REFACTOR_PLAN.md`, nhưng cập nhật theo trạng thái hiện tại (gRPC-first).

## Status

- Phase 0: Preparation — DONE
- Phase 1: Identity Service — DONE (Identity gRPC + token validation)
- Phase 2: Customer/Product/Warehouse — DONE (gRPC services + API Gateway REST→gRPC)
- Phase 3: Inventory + Documents — DONE (gRPC services + API Gateway REST→gRPC + event hooks placeholder)
- Phase 4: Audit + Reporting — DONE (gRPC services + API Gateway REST→gRPC)
- Phase 5: AI Service — DONE (gRPC service + API Gateway REST→gRPC)
- Phase 6: Harden API Gateway (Core) — IN PROGRESS
- Phase 7: Observability & Reliability — TODO
- Phase 8: Docker/Compose “Run For Real” — TODO
- Phase 9: CI + Contract/E2E Migration — TODO

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

- Add contract/e2e tests against API Gateway + gRPC stack
- Migrate GitHub Actions integration/contract tests từ `Services/wms-monolith` sang root stack
- Keep `Services/wms-monolith/tests/refactor_guard` làm safety net cho đến khi retire monolith hoàn toàn
