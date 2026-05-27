# Observability Baseline

Phase 12 standardizes trace context, metrics, and structured logs across the gRPC-first stack.

## Trace Context

- Incoming HTTP requests may provide W3C `traceparent`.
- API Gateway creates a valid `traceparent` when the caller does not provide one.
- API Gateway returns `traceparent` on HTTP responses.
- API Gateway propagates `traceparent` and `x-request-id` to downstream gRPC calls.
- gRPC services read inbound `traceparent`, create child span IDs, and include `trace_id`/`span_id` in JSON logs.

`x-request-id` remains the human-friendly correlation id. `traceparent` is the machine-friendly W3C context for OpenTelemetry-compatible tracing.

## Metrics

- API Gateway exposes Prometheus-style metrics at `/metrics`.
- Service HTTP scaffolds expose `/metrics`.
- gRPC server interceptors record request counts and duration summaries in the shared metrics registry.
- Saved production queries live in `deploy/kubernetes/examples/observability-queries.md` and cover
  request rate, error rate, latency, Redis stream lag, DLQ depth, and replay status.

## Logs

JSON logs include:

- `request_id`
- `trace_id`
- `span_id`
- HTTP/gRPC method and status
- duration in milliseconds

## OTLP Readiness

Root compose exports:

- `OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317`
- `OTEL_TRACES_EXPORTER=otlp`

Root compose runs Jaeger all-in-one as `otel-collector`, so services can export OTLP directly while
keeping the existing endpoint name.

Jaeger UI:

- `http://localhost:16686`

To inspect one request:

1. Send the request with a human-friendly `X-Request-ID`, for example `jaeger-customers-001`.
2. Open Jaeger UI.
3. Select the service, for example `api-gateway`.
4. Click **Find Traces**.
5. Open the trace and inspect the span tree.

Example span tree for `GET /api/v1/customers`:

- `GET /api/v1/customers` from `api-gateway`
- `/wms.identity.v1.IdentityService/ValidateToken` from `identity-service`
- `/wms.customer.v1.CustomerService/ListCustomers` from `customer-service`

`x-request-id` remains the human-friendly log correlation id. Jaeger/OTLP uses the W3C
`traceparent` trace id to group spans visually.
