# Observability Queries

Saved PromQL queries for the production-readiness release gates.

## Gateway

Request rate:

```promql
sum(rate(http_requests_total{job="api-gateway"}[5m])) by (method, route, status)
```

Error rate:

```promql
sum(rate(http_requests_total{job="api-gateway",status=~"5.."}[5m]))
/
sum(rate(http_requests_total{job="api-gateway"}[5m]))
```

p95 latency:

```promql
histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{job="api-gateway"}[5m])) by (le, route))
```

## Events

Redis stream lag:

```promql
redis_stream_length{stream="wms.events"}
```

DLQ depth:

```promql
redis_stream_length{stream=~"wms.events.(audit|inventory|reporting|ai).dlq"}
```

Consumer replay status:

```promql
redis_stream_length{stream="wms.events.replay"}
```

Consumer processing rate:

```promql
sum(rate(grpc_server_requests_total{service=~"audit-service|inventory-service|reporting-service"}[5m])) by (service, grpc_status)
```

## Deployment Gate Thresholds

- Gateway 5xx rate stays below 1% for 10 minutes.
- Gateway p95 latency stays within the current SLO budget.
- `wms.events` stream length does not grow for two consecutive check windows.
- Every service-owned DLQ stream is zero before traffic shift.
- `wms.events.replay` is zero unless a replay window is explicitly in progress.
