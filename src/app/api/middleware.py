"""Custom middleware: audit logging and rate limiting glue."""

from __future__ import annotations

import time

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette import status

from app.api.security import rate_limiter
from app.core.database import SessionLocal
from app.core.logging import get_logger
from app.infrastructure.persistence.models import AuditLogModel

logger = get_logger(__name__)


async def audit_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = None
    try:
        response = await call_next(request)
        return response
    finally:
        try:
            latency_ms = int((time.perf_counter() - start) * 1000)
            db = SessionLocal()
            user_id = None
            user = getattr(request.state, "user", None)
            if user:
                user_id = getattr(user, "user_id", None)
            log = AuditLogModel(
                user_id=user_id,
                path=request.url.path,
                method=request.method,
                status_code=response.status_code if response else 500,
                client_ip=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
                latency_ms=latency_ms,
            )
            db.add(log)
            db.commit()
        except Exception as exc:
            logger.warning(f"Failed to write audit log: {exc}")
        finally:
            try:
                db.close()
            except Exception:
                pass


async def rate_limit_middleware(request: Request, call_next):
    if request.url.path in {"/health", "/docs", "/redoc"}:
        return await call_next(request)
    client_ip = request.client.host if request.client else "unknown"
    allowed = await rate_limiter.check_rate_limit(client_ip)
    if not allowed:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": "Rate limit exceeded. Try later."},
        )
    return await call_next(request)

