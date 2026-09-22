from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from inventory_service.scheduler import (
    start_reservation_expiry_scheduler,
    stop_reservation_expiry_scheduler,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    start_reservation_expiry_scheduler(interval_seconds=300.0)
    try:
        yield
    finally:
        await stop_reservation_expiry_scheduler()


def create_app() -> FastAPI:
    app = FastAPI(title="Inventory Service", version="0.1.0", lifespan=lifespan)
    from shared_utils.observability import METRICS, http_metrics_middleware

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "healthy"}

    @app.get("/metrics")
    async def metrics() -> str:
        return METRICS.render_prometheus(prefix="inventory_service")

    app.middleware("http")(http_metrics_middleware(service="inventory-service"))
    return app
