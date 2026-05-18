from __future__ import annotations

import os
import time
import uuid

from fastapi import HTTPException
from fastapi import Request


async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
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
