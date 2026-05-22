# Load And Chaos Checks

Run these checks after the migration jobs and before shifting production traffic.

## Smoke

```bash
curl -fsS https://wms.example.com/health
curl -fsS https://wms.example.com/openapi.json >/dev/null
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

## Chaos

Run one failure at a time:

- Restart one backend gRPC deployment and confirm gateway returns bounded 503/504 responses.
- Pause `audit-service` and confirm Redis stream length stays below the alert threshold.
- Rotate `wms-grpc-mtls` cert material and confirm pods reload through rollout or volume update.

Do not include `ai-service` in these checks unless the release explicitly enables the AI
overlay.
