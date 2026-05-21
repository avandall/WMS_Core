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

The current baseline is dependency-light and W3C-compatible. Adding the OpenTelemetry SDK/exporter later should not require changing propagation contracts.
