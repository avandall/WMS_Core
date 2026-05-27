# Load And Chaos Checks

Run these checks after the migration jobs and before shifting production traffic.

## Smoke

```bash
curl -fsS https://wms.example.com/health
curl -fsS https://wms.example.com/openapi.json >/dev/null
```

## Auth Gate

Use a non-production release-test account and verify JWT validation through the gateway:

```bash
TOKEN="$(./ops/get-release-test-token.sh)"
curl -fsS -H "Authorization: Bearer ${TOKEN}" https://wms.example.com/api/v1/customers >/dev/null
```

## Core Business Gates

Customer flow:

```bash
curl -fsS -H "Authorization: Bearer ${TOKEN}" https://wms.example.com/api/v1/customers >/dev/null
```

Document/inventory flow:

```bash
curl -fsS -H "Authorization: Bearer ${TOKEN}" https://wms.example.com/api/v1/inventory >/dev/null
curl -fsS -H "Authorization: Bearer ${TOKEN}" https://wms.example.com/api/v1/documents >/dev/null
```

Async lag gate:

```bash
promtool query instant "$PROMETHEUS_URL" 'redis_stream_length{stream="wms.events"}'
promtool query instant "$PROMETHEUS_URL" 'redis_stream_length{stream=~"wms.events.(audit|inventory|reporting|ai).dlq"}'
```

## Load

Use the same authenticated customer flow that backs the gateway E2E tests:

```bash
k6 run load/customer-flow.js
```

Acceptance:

- p95 latency stays within the Phase 14 SLO target.
- Gateway 5xx stays below 1%.
- No circuit breaker remains open after the test window.
- Event stream lag does not grow across two consecutive windows.
- DLQ depth is zero unless an incident replay window is active.

## Chaos

Run one failure at a time:

- Restart one backend gRPC deployment and confirm gateway returns bounded 503/504 responses.
- Pause `audit-service` and confirm Redis stream length stays below the alert threshold.
- Rotate `wms-grpc-mtls` cert material and confirm pods reload through rollout or volume update.
- Rotate JWT `SECRET_KEY` in the secret manager and confirm gateway/identity roll together.

Do not include `ai-service` in these checks unless the release explicitly enables the AI
overlay.
