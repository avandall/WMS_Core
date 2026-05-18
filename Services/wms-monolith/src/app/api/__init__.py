from __future__ import annotations

"""FastAPI application package.

Docker (and some tooling) expects `app.api:app` to exist.
"""

import uuid
from typing import Any, Optional


from app.shared.core.logging import get_logger

logger = get_logger(__name__)


class _MissingDependencyApp:
    def __init__(self, exc: Exception):
        self._exc = exc

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        raise RuntimeError(
            "API dependencies are not installed (FastAPI/Pydantic/SQLAlchemy). "
            "Install project dependencies to run the server."
        ) from self._exc


def create_app() -> FastAPI:
    from contextlib import asynccontextmanager

    from fastapi import FastAPI, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse

    from app.api.middleware import audit_middleware, rate_limit_middleware
    from app.api.v1.router import router as v1_router
    from app.shared.core.database import check_db_connection, init_db
    from app.shared.core.logging import clear_request_id, set_request_id, setup_logging
    from app.shared.core.settings import settings
    from app.shared.domain.business_exceptions import DomainError, EntityNotFoundError, ValidationError

    setup_logging(level="INFO")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if settings.testing:
            logger.info("Skipping init_db() because settings.testing=True")
            yield
            return
        init_db()
        yield

    app = FastAPI(
        title=settings.title,
        description=settings.description,
        version=settings.version,
        debug=settings.debug,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
    )

    app.middleware("http")(rate_limit_middleware)
    app.middleware("http")(audit_middleware)

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        set_request_id(request_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            clear_request_id()

    @app.get("/health", tags=["Health Check"])
    async def health_check():
        db_healthy = check_db_connection()
        status = "healthy" if db_healthy else "unhealthy"
        status_code = 200 if db_healthy else 503
        return JSONResponse(
            status_code=status_code,
            content={
                "status": status,
                "database": "connected" if db_healthy else "disconnected",
                "version": settings.version,
            },
        )

    @app.get("/", tags=["Root"])
    async def root():
        return {
            "message": "Welcome to Warehouse Management System API",
            "version": settings.version,
            "documentation": "/docs",
            "health_check": "/health",
        }

    @app.exception_handler(DomainError)
    async def domain_error_handler(_request: Request, exc: DomainError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(EntityNotFoundError)
    async def entity_not_found_handler(_request: Request, exc: EntityNotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ValidationError)
    async def validation_error_handler(_request: Request, exc: ValidationError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    # Backward compatible (non-versioned) API prefix:
    app.include_router(v1_router, prefix="/api")
    # Versioned alias:
    app.include_router(v1_router, prefix="/api/v1")

    logger.info("FastAPI app created")
    return app


try:
    app: Any = create_app()
except ModuleNotFoundError as exc:
    # Allow `import app.api` in minimal environments (smoke tests, tooling).
    app = _MissingDependencyApp(exc)
except Exception as exc:
    # Keep import-time failures explicit when dependencies exist but config is broken.
    raise

__all__ = ["app", "create_app"]
