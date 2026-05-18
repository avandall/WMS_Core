from __future__ import annotations

import os
import time
import uuid

from fastapi import HTTPException
from fastapi import Request

from api_gateway.observability import METRICS, json_log


async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    start = time.monotonic()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    duration_ms = (time.monotonic() - start) * 1000.0
    METRICS.observe(
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration_ms=duration_ms,
    )
    json_log(
        level="info",
        message="http_request",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration_ms=duration_ms,
    )
    return response


_rate_state: dict[str, tuple[float, int]] = {}


async def rate_limit_middleware(request: Request, call_next):
    # Simple in-memory fixed-window rate limiter. Good enough for dev; replace with Redis later.
    rps = float(os.getenv("RATE_LIMIT_RPS", "10"))
    if rps <= 0:
        return await call_next(request)

    now = time.monotonic()
    window = 1.0
    client = request.client.host if request.client else "unknown"

    start, count = _rate_state.get(client, (now, 0))
    if now - start >= window:
        start, count = now, 0
    count += 1
    _rate_state[client] = (start, count)

    if count > int(rps * window):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    return await call_next(request)
