from __future__ import annotations

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlencode

import grpc
import httpx
import jwt
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
        
        secret_key = os.getenv("SECRET_KEY")
        if not secret_key or secret_key == "replace-with-render-secret":
            return JSONResponse(status_code=500, content={"detail": "JWT secret key is not configured"})
            
        algorithm = os.getenv("JWT_ALGORITHM", "HS256")
        
        if path == "auth/refresh" and request.method == "POST":
            payload = await request.json()
            refresh_token = payload.get("refresh_token") or ""
            if not refresh_token:
                return JSONResponse(status_code=401, content={"detail": "Missing refresh token"})
            try:
                decoded = jwt.decode(refresh_token, secret_key, algorithms=[algorithm])
                if decoded.get("type") != "refresh":
                    return JSONResponse(status_code=401, content={"detail": "Invalid token type"})
                
                user_id = decoded.get("sub")
                if not user_id:
                    return JSONResponse(status_code=401, content={"detail": "Invalid token: missing subject"})
                
                # Fetch latest user details and role from identity service to detect role changes/deactivation
                from api_gateway.gen.wms.identity.v1 import identity_pb2, identity_pb2_grpc
                from api_gateway.grpc_security import configured_grpc_channel
                with configured_grpc_channel(os.getenv("IDENTITY_GRPC_ADDR", "identity-service:50051")) as channel:
                    stub = identity_pb2_grpc.IdentityServiceStub(channel)
                    resp = stub.ValidateToken(
                        identity_pb2.ValidateTokenRequest(access_token=refresh_token),
                        timeout=5
                    )
                if not resp.valid or not resp.is_active:
                    return JSONResponse(status_code=401, content={"detail": "User is inactive or token is invalid"})
                
                role = resp.role
                expires = datetime.now(timezone.utc) + timedelta(hours=8)
                new_token = jwt.encode(
                    {"sub": str(user_id), "role": role, "exp": expires},
                    secret_key,
                    algorithm=algorithm
                )
                return JSONResponse(content={
                    "access_token": new_token,
                    "refresh_token": refresh_token,
                    "token_type": "bearer"
                })
            except Exception:
                return JSONResponse(status_code=401, content={"detail": "Invalid refresh token"})
            
        elif path == "users/me" and request.method == "GET":
            auth = request.headers.get("Authorization", "")
            if not auth.lower().startswith("bearer "):
                return JSONResponse(status_code=401, content={"detail": "Not authenticated"})
            token = auth.split(" ", 1)[1]
            try:
                from api_gateway.gen.wms.identity.v1 import identity_pb2, identity_pb2_grpc
                from api_gateway.grpc_security import configured_grpc_channel
                with configured_grpc_channel(os.getenv("IDENTITY_GRPC_ADDR", "identity-service:50051")) as channel:
                    stub = identity_pb2_grpc.IdentityServiceStub(channel)
                    resp = stub.ValidateToken(
                        identity_pb2.ValidateTokenRequest(access_token=token),
                        timeout=5
                    )
                if not resp.valid or not resp.is_active:
                    return JSONResponse(status_code=401, content={"detail": "Not authenticated"})
                    
                return JSONResponse(content={
                    "user_id": int(resp.user_id),
                    "email": resp.email,
                    "role": resp.role,
                    "full_name": resp.full_name,
                    "is_active": True,
                    "custom_permissions": [],
                })
            except Exception:
                return JSONResponse(status_code=401, content={"detail": "Not authenticated"})
            


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
        
        headers = {}
        content_type = request.headers.get("Content-Type")
        if content_type:
            headers["Content-Type"] = content_type
        else:
            headers["Content-Type"] = "application/json"
            
        authorization = request.headers.get("Authorization")
        if authorization:
            headers["Authorization"] = authorization
            
        for h_name, h_val in request.headers.items():
            if h_name.lower() in ("x-request-id", "traceparent"):
                headers[h_name] = h_val
                
        async with httpx.AsyncClient() as client:
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    content=body or None,
                    headers=headers,
                    timeout=120.0
                )
                try:
                    content = response.json()
                except Exception:
                    content = {"data": response.text}
                return JSONResponse(status_code=response.status_code, content=content)
            except httpx.HTTPStatusError as exc:
                try:
                    content = exc.response.json()
                except Exception:
                    content = {"detail": exc.response.text}
                return JSONResponse(status_code=exc.response.status_code, content=content)
            except Exception as exc:
                return JSONResponse(status_code=502, content={"detail": str(exc)})

    return app
