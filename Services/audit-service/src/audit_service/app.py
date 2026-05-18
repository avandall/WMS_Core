from __future__ import annotations

from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="Audit Service", version="0.1.0")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "healthy"}

    return app

