# Resilience and SLO Readiness

Phase 14 defines the first production-readiness baseline for latency, failure handling, and
event-consumer backpressure.

## SLO Baseline

Initial API Gateway targets:

| Endpoint class | Availability | Latency target |
| --- | ---: | ---: |
| Health and metrics | 99.9% | p95 <= 250ms |
| CRUD/read APIs | 99.5% | p95 <= 750ms |
| Reporting/warehouse analytics | 99.0% | p95 <= 3s |
| AI endpoints | 98.5% | p95 <= 10s |

These targets are intentionally conservative for the local/dev stack. Phase 17 should turn
them into deployment alerts and dashboards.

## Gateway Timeout And Retry Policy

Gateway deadlines are controlled by env:

```bash
GRPC_TIMEOUT_FAST=5
GRPC_TIMEOUT_DEFAULT=10
GRPC_TIMEOUT_SLOW=30
GRPC_TIMEOUT_AI=60
```

Idempotent gRPC calls use bounded retry with exponential backoff:

```bash
GRPC_RETRY_ATTEMPTS=2
GRPC_RETRY_BACKOFF_SECONDS=0.05
```

Only retryable gRPC status codes are retried:

- `UNAVAILABLE`
- `DEADLINE_EXCEEDED`
- `RESOURCE_EXHAUSTED`

Mutating calls keep a single downstream attempt to avoid duplicate writes.

## Circuit Breaker

Idempotent gateway calls are guarded by an in-process circuit breaker:

```bash
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
CIRCUIT_BREAKER_RECOVERY_SECONDS=15
```

Set `CIRCUIT_BREAKER_FAILURE_THRESHOLD=0` to disable it for local debugging. When open,
the gateway maps the failure as downstream `UNAVAILABLE` through the existing gRPC-to-HTTP
error handling path.

## Event Consumer Backpressure

Audit event consumption uses bounded reads and a stream-length guard:

```bash
AUDIT_EVENT_CONSUMER_BLOCK_MS=5000
AUDIT_EVENT_CONSUMER_BATCH_SIZE=20
AUDIT_EVENT_CONSUMER_MAX_STREAM_LENGTH=10000
```

When the stream exceeds the max length, the consumer logs a warning and backs off before
reading the next batch. Durable consumer groups, dead-letter queues, and replay tooling are
still deferred to deployment/ops hardening.

## Failure Testing

Current E2E stack exercises the gateway, identity service, customer service, and event bus.
Manual chaos check for Phase 14:

```bash
docker compose up -d identity-service customer-service api-gateway
docker compose stop customer-service
curl -i http://localhost:8000/api/v1/customers
```

Expected behavior: the gateway returns a bounded `503`/`504` style failure with
`x-request-id` and `traceparent`, rather than hanging indefinitely.
