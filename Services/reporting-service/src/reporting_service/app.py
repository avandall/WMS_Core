from __future__ import annotations

from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="Reporting Service", version="0.1.0")
    from shared_utils.observability import METRICS, http_metrics_middleware

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "healthy"}

    @app.get("/metrics")
    async def metrics() -> str:
        return METRICS.render_prometheus(prefix="reporting_service")

    app.middleware("http")(http_metrics_middleware(service="reporting-service"))
    return app
