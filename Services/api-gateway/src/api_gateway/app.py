from __future__ import annotations

from fastapi import FastAPI

from api_gateway.routes import router as v1_router


def create_app() -> FastAPI:
    app = FastAPI(title="API Gateway", version="0.1.0")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "healthy"}

    app.include_router(v1_router)
    return app
