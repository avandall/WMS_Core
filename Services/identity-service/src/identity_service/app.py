from __future__ import annotations

from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="Identity Service", version="0.1.0")

    # Temporary: reuse extracted monolith routers while refactoring.
    from app.api.v1.router import router as v1_router
    from shared_utils.observability import METRICS, http_metrics_middleware

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "healthy"}

    @app.get("/metrics")
    async def metrics() -> str:
        return METRICS.render_prometheus(prefix="identity_service")

    app.middleware("http")(http_metrics_middleware(service="identity-service"))
    app.include_router(v1_router, prefix="/api/v1")
    return app
