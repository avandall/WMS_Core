# Roadmap (Long-term)

Roadmap dựa trên `MICROSERVICES_REFACTOR_PLAN.md`, nhưng cập nhật theo trạng thái hiện tại (gRPC-first).

## Status

- Phase 0: Preparation — DONE
- Phase 1: Identity Service — DONE (Identity gRPC + token validation)
- Phase 2: Customer/Product/Warehouse — DONE (gRPC services + API Gateway REST→gRPC)
- Phase 3: Inventory + Documents — DONE (gRPC services + API Gateway REST→gRPC + event hooks placeholder)
- Phase 4: Audit + Reporting — DONE (gRPC services + API Gateway REST→gRPC)
- Phase 5: AI Service — DONE (gRPC service + API Gateway REST→gRPC)
- Phase 6: Harden API Gateway — TODO

## Phase 6 TODO checklist

- Replace ad-hoc REST payload dicts with Pydantic DTOs in `api-gateway`
- Centralize authz/permissions in gateway (not only authn)
- Add observability: structured logs + tracing (request-id propagation), metrics
- Add rate limiting/caching policy
- Add contract/e2e tests against API Gateway + gRPC stack
- Replace placeholder compose images with real Dockerfiles per service (or a dev compose that runs uvicorn/grpc servers)
- Migrate CI integration/contract tests from `Services/wms-monolith` to API Gateway stack

