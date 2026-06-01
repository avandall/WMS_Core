from __future__ import annotations

import os
import re
from pathlib import Path

import httpx


ROOT_DIR = Path(__file__).resolve().parents[2]
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8000").rstrip("/")


def _gateway_openapi_document() -> dict:
    try:
        response = httpx.get(f"{GATEWAY_URL}/openapi.json", timeout=10.0)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError:
        app_source = (ROOT_DIR / "Services/api-gateway/src/api_gateway/app.py").read_text()
        routes_source = (ROOT_DIR / "Services/api-gateway/src/api_gateway/routes.py").read_text()
        title_match = re.search(r"FastAPI\(title=\"([^\"]+)\"", app_source)
        route_paths = {
            f"/api/v1{match}"
            for match in re.findall(
                r"@router\.(?:get|post|put|patch|delete)\(\s*(?:\n\s*)?\"([^\"]+)\"",
                routes_source,
            )
        }
        return {
            "info": {"title": title_match.group(1) if title_match else ""},
            "paths": {path: {} for path in route_paths},
        }


def test_gateway_openapi_exposes_microservice_surface() -> None:
    document = _gateway_openapi_document()
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
    title = _gateway_openapi_document()["info"]["title"].lower()
    assert "monolith" not in title
