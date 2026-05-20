from __future__ import annotations

import os

import httpx


GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8000").rstrip("/")


def test_gateway_openapi_exposes_microservice_surface() -> None:
    response = httpx.get(f"{GATEWAY_URL}/openapi.json", timeout=10.0)
    assert response.status_code == 200

    document = response.json()
    assert document["info"]["title"] == "API Gateway"

    paths = set(document["paths"])
    expected_paths = {
        "/api/v1/customers",
        "/api/v1/products",
        "/api/v1/warehouses",
        "/api/v1/inventory",
        "/api/v1/documents",
        "/api/v1/audit-events",
        "/api/v1/reports/inventory",
        "/api/v1/ai/query",
    }
    assert expected_paths.issubset(paths)


def test_gateway_openapi_has_no_legacy_monolith_title() -> None:
    response = httpx.get(f"{GATEWAY_URL}/openapi.json", timeout=10.0)
    assert response.status_code == 200

    title = response.json()["info"]["title"].lower()
    assert "monolith" not in title
