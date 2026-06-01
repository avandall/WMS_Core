"""Dashboard integration for the gateway-backed WMS backend."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from time import perf_counter
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_GATEWAY_URL = os.getenv("API_GATEWAY_URL", "http://localhost:8000").rstrip("/")
DASHBOARD_GATEWAY_TIMEOUT = float(os.getenv("DASHBOARD_GATEWAY_TIMEOUT", "20"))


@dataclass(slots=True)
class GatewayResponse:
    success: bool
    payload: dict[str, Any]
    detail: str = ""
    status_code: int | None = None
    processing_time: float | None = None
    timestamp: str | None = None


def _forward_headers(headers: Any | None) -> dict[str, str]:
    forwarded: dict[str, str] = {}
    if not headers:
        return forwarded
    getter = getattr(headers, "get", None)
    if not callable(getter):
        return forwarded
    for key in ("Authorization", "X-Request-ID", "traceparent"):
        value = getter(key)
        if value:
            forwarded[key] = value
    return forwarded


def _request_json(
    *,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = DASHBOARD_GATEWAY_TIMEOUT,
) -> GatewayResponse:
    url = f"{API_GATEWAY_URL}{path}"
    request_headers = {"Content-Type": "application/json"}
    if headers:
        request_headers.update(headers)
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(url, data=body, method=method, headers=request_headers)

    started = perf_counter()
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8") or "{}"
            payload = json.loads(raw)
            return GatewayResponse(
                success=True,
                payload=payload if isinstance(payload, dict) else {"data": payload},
                processing_time=perf_counter() - started,
                timestamp=datetime.now().isoformat(),
            )
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace") if exc.fp else str(exc)
        try:
            payload = json.loads(detail) if detail.startswith("{") else {}
        except Exception:
            payload = {}
        return GatewayResponse(
            success=False,
            payload=payload,
            detail=detail,
            status_code=exc.code,
            processing_time=perf_counter() - started,
            timestamp=datetime.now().isoformat(),
        )
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        return GatewayResponse(
            success=False,
            payload={},
            detail=str(exc),
            processing_time=perf_counter() - started,
            timestamp=datetime.now().isoformat(),
        )


def _response_dict(response: GatewayResponse) -> dict[str, Any]:
    data = dict(response.payload)
    data.setdefault("success", response.success)
    if response.detail and "detail" not in data:
        data["detail"] = response.detail
    if response.status_code is not None:
        data["status_code"] = response.status_code
    if response.processing_time is not None:
        data["processing_time"] = response.processing_time
    if response.timestamp is not None:
        data["timestamp"] = response.timestamp
    return data


def _unsupported(feature: str) -> dict[str, Any]:
    return {
        "success": False,
        "detail": f"{feature} is not exposed by the dashboard integration yet.",
    }


def initialize_gateway() -> bool:
    health = _request_json(method="GET", path="/health")
    return bool(health.success)


def get_gateway_url() -> str | None:
    return API_GATEWAY_URL if initialize_gateway() else None


def _gateway_get(path: str, headers: Any | None = None, query: dict[str, Any] | None = None) -> dict[str, Any]:
    if query:
        path = f"{path}?{urlencode({k: v for k, v in query.items() if v is not None})}"
    return _response_dict(_request_json(method="GET", path=path, headers=_forward_headers(headers)))


def _gateway_post(path: str, payload: dict[str, Any], headers: Any | None = None) -> dict[str, Any]:
    return _response_dict(_request_json(method="POST", path=path, payload=payload, headers=_forward_headers(headers)))


def _gateway_patch(path: str, payload: dict[str, Any], headers: Any | None = None) -> dict[str, Any]:
    return _response_dict(_request_json(method="PATCH", path=path, payload=payload, headers=_forward_headers(headers)))


def _gateway_put(path: str, payload: dict[str, Any], headers: Any | None = None) -> dict[str, Any]:
    return _response_dict(_request_json(method="PUT", path=path, payload=payload, headers=_forward_headers(headers)))


def _gateway_delete(path: str, headers: Any | None = None) -> dict[str, Any]:
    return _response_dict(_request_json(method="DELETE", path=path, headers=_forward_headers(headers)))


# Customers
def list_customers(headers: Any | None = None) -> dict[str, Any]:
    return _gateway_get("/api/v1/customers", headers=headers)


def create_customer(payload: dict[str, Any], headers: Any | None = None) -> dict[str, Any]:
    return _gateway_post("/api/v1/customers", payload, headers=headers)


def get_customer(customer_id: int, headers: Any | None = None) -> dict[str, Any]:
    return _gateway_get(f"/api/v1/customers/{customer_id}", headers=headers)


def update_customer(customer_id: int, payload: dict[str, Any], headers: Any | None = None) -> dict[str, Any]:
    return _gateway_patch(f"/api/v1/customers/{customer_id}", payload, headers=headers)


def update_customer_debt(customer_id: int, amount: float, headers: Any | None = None) -> dict[str, Any]:
    return _gateway_patch(f"/api/v1/customers/{customer_id}/debt", {"amount": amount}, headers=headers)


def list_customer_purchases(customer_id: int, headers: Any | None = None) -> dict[str, Any]:
    return _gateway_get(f"/api/v1/customers/{customer_id}/purchases", headers=headers)


# Products
def list_products(headers: Any | None = None) -> dict[str, Any]:
    return _gateway_get("/api/v1/products", headers=headers)


def create_product(payload: dict[str, Any], headers: Any | None = None) -> dict[str, Any]:
    return _gateway_post("/api/v1/products", payload, headers=headers)


def get_product(product_id: int, headers: Any | None = None) -> dict[str, Any]:
    return _gateway_get(f"/api/v1/products/{product_id}", headers=headers)


def update_product(product_id: int, payload: dict[str, Any], headers: Any | None = None) -> dict[str, Any]:
    return _gateway_put(f"/api/v1/products/{product_id}", payload, headers=headers)


def delete_product(product_id: int, headers: Any | None = None) -> dict[str, Any]:
    return _gateway_delete(f"/api/v1/products/{product_id}", headers=headers)


# Warehouses
def list_warehouses(headers: Any | None = None) -> dict[str, Any]:
    return _gateway_get("/api/v1/warehouses", headers=headers)


def create_warehouse(payload: dict[str, Any], headers: Any | None = None) -> dict[str, Any]:
    return _gateway_post("/api/v1/warehouses", payload, headers=headers)


def get_warehouse(warehouse_id: int, headers: Any | None = None) -> dict[str, Any]:
    return _gateway_get(f"/api/v1/warehouses/{warehouse_id}", headers=headers)


def delete_warehouse(warehouse_id: int, headers: Any | None = None) -> dict[str, Any]:
    return _gateway_delete(f"/api/v1/warehouses/{warehouse_id}", headers=headers)


def transfer_warehouse_inventory(warehouse_id: int, to_warehouse_id: int, headers: Any | None = None) -> dict[str, Any]:
    return _gateway_post(
        f"/api/v1/warehouses/{warehouse_id}/transfer",
        {"to_warehouse_id": to_warehouse_id},
        headers=headers,
    )


def get_system_overview(headers: Any | None = None) -> dict[str, Any]:
    return _gateway_get("/api/v1/warehouse-operations/system-overview", headers=headers)


def get_inventory_health(headers: Any | None = None) -> dict[str, Any]:
    return _gateway_get("/api/v1/warehouse-operations/inventory-health", headers=headers)


def optimize_distribution(product_id: int, headers: Any | None = None) -> dict[str, Any]:
    return _gateway_get(f"/api/v1/warehouse-operations/optimize-distribution/{product_id}", headers=headers)


# Inventory
def list_inventory(headers: Any | None = None) -> dict[str, Any]:
    return _gateway_get("/api/v1/inventory", headers=headers)


def list_inventory_by_warehouse(headers: Any | None = None) -> dict[str, Any]:
    return _gateway_get("/api/v1/inventory/by-warehouse", headers=headers)


def get_inventory_quantity(product_id: int, headers: Any | None = None) -> dict[str, Any]:
    return _gateway_get(f"/api/v1/inventory/{product_id}", headers=headers)


# Documents
def create_import_document(payload: dict[str, Any], headers: Any | None = None) -> dict[str, Any]:
    return _gateway_post("/api/v1/documents/import", payload, headers=headers)


def create_export_document(payload: dict[str, Any], headers: Any | None = None) -> dict[str, Any]:
    return _gateway_post("/api/v1/documents/export", payload, headers=headers)


def create_sale_document(payload: dict[str, Any], headers: Any | None = None) -> dict[str, Any]:
    return _gateway_post("/api/v1/documents/sale", payload, headers=headers)


def create_transfer_document(payload: dict[str, Any], headers: Any | None = None) -> dict[str, Any]:
    return _gateway_post("/api/v1/documents/transfer", payload, headers=headers)


def post_document(document_id: int, payload: dict[str, Any], headers: Any | None = None) -> dict[str, Any]:
    return _gateway_post(f"/api/v1/documents/{document_id}/post", payload, headers=headers)


def get_document(document_id: int, headers: Any | None = None) -> dict[str, Any]:
    return _gateway_get(f"/api/v1/documents/{document_id}", headers=headers)


def list_documents(headers: Any | None = None, *, doc_type: str | None = None, page: int = 1, page_size: int = 20) -> dict[str, Any]:
    return _gateway_get(
        "/api/v1/documents",
        headers=headers,
        query={"doc_type": doc_type, "page": page, "page_size": page_size},
    )


def delete_document(document_id: int, headers: Any | None = None) -> dict[str, Any]:
    return _gateway_delete(f"/api/v1/documents/{document_id}", headers=headers)


# Audit
def list_audit_events(headers: Any | None = None, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
    return _gateway_get("/api/v1/audit-events", headers=headers, query={"limit": limit, "offset": offset})


def get_audit_event(event_id: int, headers: Any | None = None) -> dict[str, Any]:
    return _gateway_get(f"/api/v1/audit-events/{event_id}", headers=headers)


# Reports
def report_inventory(headers: Any | None = None, *, warehouse_id: int | None = None, low_stock_threshold: int = 10) -> dict[str, Any]:
    return _gateway_get(
        "/api/v1/reports/inventory",
        headers=headers,
        query={"warehouse_id": warehouse_id, "low_stock_threshold": low_stock_threshold},
    )


def report_inventory_list(headers: Any | None = None) -> dict[str, Any]:
    return _gateway_get("/api/v1/reports/inventory/list", headers=headers)


def report_warehouse(headers: Any | None = None, *, warehouse_id: int, start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
    return _gateway_get(
        f"/api/v1/reports/warehouse/{warehouse_id}",
        headers=headers,
        query={"start_date": start_date, "end_date": end_date},
    )


def report_documents(headers: Any | None = None, *, start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
    return _gateway_get("/api/v1/reports/documents", headers=headers, query={"start_date": start_date, "end_date": end_date})


def report_product(headers: Any | None = None, *, product_id: int, start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
    return _gateway_get(
        f"/api/v1/reports/product/{product_id}",
        headers=headers,
        query={"start_date": start_date, "end_date": end_date},
    )


def report_sales(
    headers: Any | None = None,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    customer_id: int | None = None,
    salesperson: str | None = None,
) -> dict[str, Any]:
    return _gateway_get(
        "/api/v1/reports/sales",
        headers=headers,
        query={
            "start_date": start_date,
            "end_date": end_date,
            "customer_id": customer_id,
            "salesperson": salesperson,
        },
    )


# AI
def query_ai(question: str, mode: str = "auto", headers: Any | None = None) -> dict[str, Any]:
    return _gateway_post("/api/v1/ai/query", {"question": question, "mode": mode}, headers=headers)


def ai_status(headers: Any | None = None) -> dict[str, Any]:
    return _gateway_get("/api/v1/ai/status", headers=headers)


def handle_ai_query(data, headers: Any | None = None) -> dict[str, Any]:
    """Backward compatible wrapper for existing callers."""
    question = (data or {}).get("question", "")
    mode = (data or {}).get("mode", "auto")
    if not question:
        return {"success": False, "detail": "Question is required"}
    return query_ai(question=question, mode=mode, headers=headers)


def handle_ai_engine_info(headers: Any | None = None) -> dict[str, Any]:
    return ai_status(headers=headers)


def handle_ai_document_upload(data, headers: Any | None = None) -> dict[str, Any]:
    return _unsupported("Document upload")


def handle_ai_init_sample(headers: Any | None = None) -> dict[str, Any]:
    return _unsupported("Sample initialization")


def handle_ai_document_stats(headers: Any | None = None) -> dict[str, Any]:
    return _unsupported("Document stats")


def add_ai_routes_to_flask(app):
    """Compatibility routes for older dashboard integrations."""
    from flask import jsonify, request

    @app.route("/api/ai/query", methods=["POST"])
    def api_ai_query():
        try:
            result = handle_ai_query(request.get_json() or {}, headers=request.headers)
            return jsonify(result)
        except Exception as exc:
            return jsonify({"success": False, "detail": str(exc)}), 500

    @app.route("/api/ai/engine/info", methods=["GET"])
    def api_ai_engine_info():
        try:
            result = handle_ai_engine_info(headers=request.headers)
            return jsonify(result)
        except Exception as exc:
            return jsonify({"success": False, "detail": str(exc)}), 500


def add_ai_routes_to_fastapi(app):
    """Compatibility routes for older dashboard integrations."""
    from fastapi import HTTPException, Request
    from pydantic import BaseModel

    class QueryRequest(BaseModel):
        question: str
        mode: str = "auto"

    @app.post("/api/ai/query")
    async def api_ai_query(request: Request, payload: QueryRequest):
        try:
            return handle_ai_query(payload.model_dump(), headers=request.headers)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @app.get("/api/ai/engine/info")
    async def api_ai_engine_info(request: Request):
        try:
            return handle_ai_engine_info(headers=request.headers)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))


if __name__ == "__main__":
    try:
        from flask import Flask
    except Exception as exc:  # pragma: no cover - convenience only
        raise SystemExit(f"Flask is not installed: {exc}") from exc

    app = Flask(__name__)
    add_ai_routes_to_flask(app)
    app.run(debug=True, port=8080)
