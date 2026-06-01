from __future__ import annotations

import os

import grpc
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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
    value = os.getenv(name, default)
    return [item.strip() for item in value.split(",") if item.strip()]


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def create_app() -> FastAPI:
    app = FastAPI(title="API Gateway", version="0.1.0")

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

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "healthy"}

    @app.get("/metrics")
    async def metrics() -> str:
        return METRICS.render_prometheus()

    @app.exception_handler(grpc.RpcError)
    async def grpc_error_handler(_request, exc: grpc.RpcError) -> JSONResponse:
        http_exc = grpc_http_exception(exc)
        return JSONResponse(status_code=http_exc.status_code, content={"detail": http_exc.detail})

    app.include_router(v1_router)
    return app
