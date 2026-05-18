from __future__ import annotations

from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="Identity Service", version="0.1.0")

    # Temporary: reuse extracted monolith routers while refactoring.
    from app.api.v1.router import router as v1_router

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "healthy"}

    app.include_router(v1_router, prefix="/api/v1")
    return app
