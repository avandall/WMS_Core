from __future__ import annotations

import os
import uuid

import httpx


GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8000").rstrip("/")
ACCESS_TOKEN = os.getenv("E2E_ACCESS_TOKEN", "")


def _headers() -> dict[str, str]:
    assert ACCESS_TOKEN, "E2E_ACCESS_TOKEN is required for gateway stack E2E tests"
    return {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "X-Request-ID": f"gateway-e2e-{uuid.uuid4().hex}",
    }


def test_gateway_health_metrics_and_openapi() -> None:
    with httpx.Client(base_url=GATEWAY_URL, timeout=10.0) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json() == {"status": "healthy"}

        metrics = client.get("/metrics")
        assert metrics.status_code == 200
        assert "api_gateway_requests_total" in metrics.text

        openapi = client.get("/openapi.json")
        assert openapi.status_code == 200
        assert openapi.json()["openapi"].startswith("3.")


def test_gateway_rejects_unauthenticated_domain_requests() -> None:
    response = httpx.get(f"{GATEWAY_URL}/api/v1/customers", timeout=10.0)
    assert response.status_code == 401


def test_customer_create_through_gateway_to_grpc_service() -> None:
    suffix = uuid.uuid4().hex[:8]
    payload = {
        "name": f"Gateway E2E Customer {suffix}",
        "email": f"gateway.e2e.customer.{suffix}@example.com",
        "phone": "555-0109",
        "address": "Gateway E2E",
    }

    with httpx.Client(base_url=GATEWAY_URL, headers=_headers(), timeout=15.0) as client:
        created = client.post("/api/v1/customers", json=payload)
        assert created.status_code == 200, created.text
        customer = created.json()
        assert customer["name"] == payload["name"]
        assert customer["email"] == payload["email"]
        assert created.headers["x-request-id"].startswith("gateway-e2e-")

        assert customer["customer_id"] > 0
