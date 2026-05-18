from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api_gateway.routes import router as v1_router
from api_gateway.middleware import rate_limit_middleware, request_id_middleware
from api_gateway.observability import METRICS


def create_app() -> FastAPI:
    app = FastAPI(title="API Gateway", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.middleware("http")(rate_limit_middleware)
    app.middleware("http")(request_id_middleware)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "healthy"}

    @app.get("/metrics")
    async def metrics() -> str:
        return METRICS.render_prometheus()

    app.include_router(v1_router)
    return app
