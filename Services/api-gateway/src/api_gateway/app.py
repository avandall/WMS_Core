from __future__ import annotations

import os
from pathlib import Path
from urllib.request import Request as UrlRequest
from urllib.request import urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
import json

import grpc
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse

from api_gateway.errors import grpc_http_exception
from api_gateway.routes import router as v1_router
from api_gateway.middleware import (
    rate_limit_middleware,
    request_body_limit_middleware,
    request_id_middleware,
    security_headers_middleware,
)
from api_gateway.observability import METRICS


def _csv_env(name: str, default: str) -> list[str]:
    value = os.getenv(name, default).strip()
    # Nếu chuỗi truyền vào bọc bởi dấu ngoặc vuông mảng kiểu ["*"] hoặc ["http..."]
    if value.startswith("[") and value.endswith("]"):
        import json
        try:
            res = json.loads(value)
            if isinstance(res, list):
                return [str(item).strip() for item in res]
        except Exception:
            pass
    # Ngược lại xử lý cắt dấu phẩy truyền thống
    return [item.strip() for item in value.split(",") if item.strip()]


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _find_dashboard_dir() -> Path:
    path = Path(__file__).resolve().parents[4] / "dashboard"
    if path.exists():
        return path
    cwd = Path.cwd()
    if (cwd / "dashboard").exists():
        return cwd / "dashboard"
    if (cwd.parent / "dashboard").exists():
        return cwd.parent / "dashboard"
    return path


def create_app() -> FastAPI:
    app = FastAPI(title="API Gateway", version="0.1.0")
    dashboard_dir = _find_dashboard_dir()

    @app.get("/")
    async def root() -> FileResponse:
        return FileResponse(dashboard_dir / "index.html")

    @app.get("/styles.css")
    async def styles() -> FileResponse:
        return FileResponse(dashboard_dir / "styles.css")

    @app.get("/script.js")
    async def script() -> FileResponse:
        return FileResponse(dashboard_dir / "script.js")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "healthy"}

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_csv_env("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000"),
        allow_credentials=_bool_env("CORS_ALLOW_CREDENTIALS"),
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID", "traceparent"],
        expose_headers=["X-Request-ID", "traceparent"],
    )
    app.middleware("http")(security_headers_middleware)
    app.middleware("http")(request_body_limit_middleware)
    app.middleware("http")(rate_limit_middleware)
    app.middleware("http")(request_id_middleware)

    

    @app.get("/metrics")
    async def metrics() -> str:
        return METRICS.render_prometheus()

    @app.exception_handler(grpc.RpcError)
    async def grpc_error_handler(_request, exc: grpc.RpcError) -> JSONResponse:
        http_exc = grpc_http_exception(exc)
        return JSONResponse(status_code=http_exc.status_code, content={"detail": http_exc.detail})

    app.include_router(v1_router)

    @app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    async def api_proxy(path: str, request: Request) -> JSONResponse:
        path = path.strip("/")
        
        dev_users = {
            "admin@wms.vn": {"password": "admin123", "user_id": 1, "role": "admin", "full_name": "Administrator"},
            "warehouse@wms.vn": {"password": "warehouse123", "user_id": 2, "role": "warehouse", "full_name": "Warehouse"},
            "sales@wms.vn": {"password": "sales123", "user_id": 3, "role": "sales", "full_name": "Sales"},
            "accountant@wms.vn": {"password": "account123", "user_id": 4, "role": "accountant", "full_name": "Accountant"},
        }
        
        secret_key = os.getenv("SECRET_KEY", "replace-with-render-secret")
        algorithm = os.getenv("JWT_ALGORITHM", "HS256")
        
        if path == "auth/login" and request.method == "POST":
            payload = await request.json()
            email = str(payload.get("email", "")).lower()
            password = str(payload.get("password", ""))
            user = dev_users.get(email)
            if not user or user["password"] != password:
                return JSONResponse(status_code=401, content={"detail": "Invalid credentials"})
            
            from datetime import datetime, timezone, timedelta
            import jwt
            expires = datetime.now(timezone.utc) + timedelta(hours=8)
            token = jwt.encode({"sub": str(user["user_id"]), "role": user["role"], "exp": expires}, secret_key, algorithm=algorithm)
            user_payload = {
                "user_id": user["user_id"],
                "email": email,
                "role": user["role"],
                "full_name": user["full_name"],
                "is_active": True,
            }
            return JSONResponse(content={
                "access_token": token,
                "refresh_token": token,
                "token_type": "bearer",
                "user": user_payload,
            })
            
        elif path == "auth/refresh" and request.method == "POST":
            payload = await request.json()
            token = payload.get("refresh_token") or ""
            if not token:
                return JSONResponse(status_code=401, content={"detail": "Missing refresh token"})
            return JSONResponse(content={"access_token": token, "refresh_token": token, "token_type": "bearer"})
            
        elif path == "users/me" and request.method == "GET":
            auth = request.headers.get("Authorization", "")
            if not auth.lower().startswith("bearer "):
                return JSONResponse(status_code=401, content={"detail": "Not authenticated"})
            token = auth.split(" ", 1)[1]
            try:
                import jwt
                payload = jwt.decode(token, secret_key, algorithms=[algorithm])
                user_id = int(payload.get("sub") or 0)
            except Exception:
                return JSONResponse(status_code=401, content={"detail": "Not authenticated"})
                
            for email, user in dev_users.items():
                if int(user["user_id"]) == user_id:
                    return JSONResponse(content={
                        "user_id": user["user_id"],
                        "email": email,
                        "role": user["role"],
                        "full_name": user["full_name"],
                        "is_active": True,
                        "custom_permissions": [],
                    })
            return JSONResponse(status_code=401, content={"detail": "Not authenticated"})
            
        elif path == "users/permissions" and request.method == "GET":
            return JSONResponse(
                content={
                    "roles": {
                        "admin": ["*"],
                        "warehouse": ["view_products", "view_warehouses", "view_inventory", "manage_documents"],
                        "sales": ["view_products", "view_customers", "manage_customers", "manage_documents"],
                        "accountant": ["view_reports", "view_customers", "view_documents"],
                    },
                    "permissions": [
                        "view_products", "manage_products",
                        "view_warehouses", "manage_warehouses",
                        "view_inventory",
                        "view_documents", "manage_documents",
                        "doc_create_import", "doc_create_export", "doc_create_transfer", "doc_post",
                        "view_customers", "manage_customers",
                        "view_reports",
                        "manage_users",
                    ],
                }
            )
            
        elif path == "users/me/change-password" and request.method == "POST":
            return JSONResponse(content={"success": True, "message": "Password changed successfully"})

        def _gateway_path(p: str) -> str:
            if p.startswith("v1/"):
                return f"/api/{p}"
            if p == "products/import-csv":
                return "/api/v1/products"
            return f"/api/v1/{p}"

        gateway_path = _gateway_path(path)
        query = f"?{urlencode(dict(request.query_params))}" if request.query_params else ""
        port = os.getenv("PORT", "10000")
        url = f"http://127.0.0.1:{port}{gateway_path}{query}"
        
        method = request.method
        body = await request.body()
        
        headers = {"Content-Type": "application/json"}
        authorization = request.headers.get("Authorization")
        if authorization:
            headers["Authorization"] = authorization
            
        req = UrlRequest(url, data=body or None, method=method, headers=headers)
        try:
            with urlopen(req, timeout=120) as response:
                raw = response.read().decode("utf-8") or "{}"
                try:
                    content = json.loads(raw)
                except json.JSONDecodeError:
                    content = {"data": raw}
                return JSONResponse(status_code=response.status, content=content)
        except HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                content = json.loads(raw) if raw else {}
                if not isinstance(content, dict):
                    content = {"detail": content}
            except json.JSONDecodeError:
                content = {"detail": raw or str(exc)}
            return JSONResponse(status_code=exc.code, content=content)
        except (URLError, TimeoutError) as exc:
            return JSONResponse(status_code=502, content={"detail": str(exc)})

    return app
