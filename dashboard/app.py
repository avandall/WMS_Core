"""Dashboard HTTP entrypoint for Docker Compose."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

import jwt
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

from dashboard.ai_engine_integration import add_ai_routes_to_fastapi, get_gateway_url


app = FastAPI(title="WMS Dashboard", version="0.1.0")
add_ai_routes_to_fastapi(app)

BASE_DIR = Path(__file__).resolve().parent
API_GATEWAY_URL = os.getenv("API_GATEWAY_URL", "http://localhost:8000").rstrip("/")
DEV_JWT_SECRET = os.getenv("DASHBOARD_DEV_JWT_SECRET", "replace-with-local-dev-secret")
DEV_JWT_ALGORITHM = os.getenv("DASHBOARD_DEV_JWT_ALGORITHM", "HS256")

DEV_USERS = {
    "admin@wms.vn": {"password": "admin123", "user_id": 1, "role": "admin", "full_name": "Administrator"},
    "warehouse@wms.vn": {"password": "warehouse123", "user_id": 2, "role": "warehouse", "full_name": "Warehouse"},
    "sales@wms.vn": {"password": "sales123", "user_id": 3, "role": "sales", "full_name": "Sales"},
    "accountant@wms.vn": {"password": "account123", "user_id": 4, "role": "accountant", "full_name": "Accountant"},
}


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(BASE_DIR / "index.html")


@app.get("/styles.css")
async def styles() -> FileResponse:
    return FileResponse(BASE_DIR / "styles.css")


@app.get("/script.js")
async def script() -> FileResponse:
    return FileResponse(BASE_DIR / "script.js")


@app.get("/api/status")
async def api_status() -> dict[str, object]:
    gateway_url = get_gateway_url()
    return {
        "service": "wms-dashboard",
        "status": "healthy" if gateway_url else "gateway-unavailable",
        "gateway_url": gateway_url,
        "routes": ["/health", "/api/ai/query", "/api/ai/engine/info"],
    }


@app.get("/health")
async def health() -> dict[str, str]:
    gateway_url = get_gateway_url()
    return {
        "status": "healthy" if gateway_url else "gateway-unavailable",
        "gateway_url": gateway_url or "",
    }


@app.post("/api/auth/login")
async def login(request: Request) -> JSONResponse:
    payload = await request.json()
    email = str(payload.get("email", "")).lower()
    password = str(payload.get("password", ""))
    user = DEV_USERS.get(email)
    if not user or user["password"] != password:
        return JSONResponse(status_code=401, content={"detail": "Invalid credentials"})

    expires = datetime.now(timezone.utc) + timedelta(hours=8)
    token = jwt.encode({"sub": str(user["user_id"]), "exp": expires}, DEV_JWT_SECRET, algorithm=DEV_JWT_ALGORITHM)
    user_payload = {
        "user_id": user["user_id"],
        "email": email,
        "role": user["role"],
        "full_name": user["full_name"],
        "is_active": True,
    }
    return JSONResponse(
        content={
            "access_token": token,
            "refresh_token": token,
            "token_type": "bearer",
            "user": user_payload,
        }
    )


@app.post("/auth/refresh")
async def refresh(request: Request) -> JSONResponse:
    payload = await request.json()
    token = payload.get("refresh_token") or ""
    if not token:
        return JSONResponse(status_code=401, content={"detail": "Missing refresh token"})
    return JSONResponse(content={"access_token": token, "refresh_token": token, "token_type": "bearer"})


@app.get("/api/users/me")
async def current_user(request: Request) -> JSONResponse:
    user = _current_dev_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"detail": "Not authenticated"})
    return JSONResponse(content=user)


@app.get("/api/users")
async def list_users() -> JSONResponse:
    users = [_public_user(email, user) for email, user in DEV_USERS.items()]
    return JSONResponse(content=users)


@app.post("/api/users")
async def create_user_stub() -> JSONResponse:
    return JSONResponse(status_code=501, content={"detail": "User creation is not exposed by the gRPC gateway yet."})


@app.get("/api/users/permissions")
async def user_permissions() -> JSONResponse:
    return JSONResponse(
        content={
            "admin": ["*"],
            "warehouse": ["view_products", "view_warehouses", "view_inventory", "manage_documents"],
            "sales": ["view_products", "view_customers", "manage_customers", "manage_documents"],
            "accountant": ["view_reports", "view_customers", "view_documents"],
        }
    )


@app.api_route("/api/users/{_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def user_management_stub(_path: str) -> JSONResponse:
    return JSONResponse(status_code=501, content={"detail": "User management is not exposed by the gRPC gateway yet."})


@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def legacy_api_proxy(path: str, request: Request) -> JSONResponse:
    return await _proxy_to_gateway(path, request)


async def _proxy_to_gateway(path: str, request: Request) -> JSONResponse:
    method = request.method
    body = await request.body()
    gateway_path = _gateway_path(path)

    if gateway_path == "/api/v1/ai/chat-db" and method == "POST":
        source_payload = _json_body(body)
        body = json.dumps(
            {
                "question": source_payload.get("message") or source_payload.get("query") or source_payload.get("question") or "",
                "mode": source_payload.get("mode", "auto"),
            }
        ).encode("utf-8")
        gateway_path = "/api/v1/ai/query"

    query = f"?{urlencode(dict(request.query_params))}" if request.query_params else ""
    url = f"{API_GATEWAY_URL}{gateway_path}{query}"
    headers = {"Content-Type": "application/json"}
    authorization = request.headers.get("Authorization")
    if authorization:
        headers["Authorization"] = authorization

    req = UrlRequest(url, data=body or None, method=method, headers=headers)
    try:
        with urlopen(req, timeout=20) as response:
            raw = response.read().decode("utf-8") or "{}"
            payload = _json_or_data(raw)
            if gateway_path == "/api/v1/ai/query" and isinstance(payload, dict):
                payload.setdefault("answer", payload.get("response", ""))
            return JSONResponse(status_code=response.status, content=payload)
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        return JSONResponse(status_code=exc.code, content=_json_or_detail(raw, str(exc)))
    except (URLError, TimeoutError) as exc:
        return JSONResponse(status_code=502, content={"detail": str(exc)})


def _gateway_path(path: str) -> str:
    path = path.strip("/")
    if path.startswith("v1/"):
        return f"/api/{path}"
    if path == "products/import-csv":
        return "/api/v1/products"
    return f"/api/v1/{path}"


def _json_body(body: bytes) -> dict[str, object]:
    if not body:
        return {}
    try:
        value = json.loads(body.decode("utf-8"))
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        return {}


def _json_or_data(raw: str) -> object:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"data": raw}


def _json_or_detail(raw: str, fallback: str) -> dict[str, object]:
    try:
        value = json.loads(raw) if raw else {}
        return value if isinstance(value, dict) else {"detail": value}
    except json.JSONDecodeError:
        return {"detail": raw or fallback}


def _current_dev_user(request: Request) -> dict[str, object] | None:
    auth = request.headers.get("Authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    token = auth.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, DEV_JWT_SECRET, algorithms=[DEV_JWT_ALGORITHM])
        user_id = int(payload.get("sub") or 0)
    except Exception:
        return None
    for email, user in DEV_USERS.items():
        if int(user["user_id"]) == user_id:
            return _public_user(email, user)
    return None


def _public_user(email: str, user: dict[str, object]) -> dict[str, object]:
    return {
        "user_id": user["user_id"],
        "email": email,
        "role": user["role"],
        "full_name": user["full_name"],
        "is_active": True,
    }


@app.exception_handler(Exception)
async def unhandled_error(_request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"success": False, "detail": str(exc)})
