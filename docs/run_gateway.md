# Run via API Gateway (REST → gRPC)

## 1) Generate gRPC stubs

`./.venv/bin/python scripts/gen_protos.py`

## 2) Start stack

Root compose exposes the API Gateway at `http://localhost:8000`.

`docker compose up -d`

Default compose does not start `ai-service`; it is behind the `ai` profile so normal dev/test
commands do not build the heavy ML image.

To include AI explicitly:

`docker compose --profile ai up -d`

Each service has its own local datastore connection in root compose. See
`docs/data_ownership.md` for the Phase 10 ownership baseline and remaining migration work.

Root compose also starts Redis Streams as `event-bus` for async domain events. See
`docs/events.md` for the Phase 11 event envelope and consumer baseline.

Gateway and gRPC services propagate W3C `traceparent` and keep `x-request-id` for human
correlation. See `docs/observability.md` for the Phase 12 baseline.

Gateway security headers, explicit CORS configuration, request body limits, and opt-in gRPC
TLS are documented in `docs/security.md`.

Timeouts, bounded retries, the gateway circuit breaker, SLO targets, and audit-consumer
backpressure are documented in `docs/resilience.md`.

Release tagging, SBOM expectations, deployment order, migration ownership, runbooks, and
API/proto versioning are documented in `docs/release_ops.md`.

Monolith retirement status and fixture ownership are documented in `docs/monolith_retirement.md`.

## 3) Notes

- Identity gRPC is used for token validation (`ValidateToken`).
- Services currently have both REST and gRPC scaffolds, but the intended public surface is API Gateway REST.
- Phase 3 adds Inventory + Documents gRPC services and exposes them via API Gateway:
  - `/api/v1/inventory/*`
  - `/api/v1/documents/*`

- Phase 4 adds Audit + Reporting gRPC services:
  - `/api/v1/audit-events/*`
  - `/api/v1/reports/*`

- Phase 5 adds AI gRPC service:
  - `/api/v1/ai/*`
  - AI is opt-in for local compose: `docker compose --profile ai up -d`
