from __future__ import annotations

import hashlib
import os
import time
import uuid

from fastapi import HTTPException
from fastapi import Request
from shared_utils.observability.otel import start_span

from api_gateway.observability import METRICS, child_trace_context, json_log, parse_traceparent


async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "camera=(), geolocation=(), microphone=()")
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    return response


async def request_body_limit_middleware(request: Request, call_next):
    if request.method in {"POST", "PUT", "PATCH"}:
        try:
            max_bytes = int(os.getenv("MAX_REQUEST_BODY_BYTES", "1048576"))
        except ValueError:
            max_bytes = 1048576
        content_length = request.headers.get("content-length")
        if max_bytes > 0 and content_length:
            try:
                body_bytes = int(content_length)
            except ValueError:
                body_bytes = 0
            if body_bytes > max_bytes:
                raise HTTPException(status_code=413, detail="Request body too large")
    return await call_next(request)


async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    trace_context = child_trace_context(parse_traceparent(request.headers.get("traceparent")))
    request.state.trace_id = trace_context.trace_id
    request.state.span_id = trace_context.span_id
    request.state.traceparent = trace_context.traceparent
    start = time.monotonic()
    status_code = 500
    try:
        with start_span(
            service_name="api-gateway",
            span_name=f"{request.method} {request.url.path}",
            trace_context=trace_context,
            attributes={
                "http.request.method": request.method,
                "url.path": request.url.path,
                "wms.request_id": request_id,
            },
        ):
            response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = request_id
        response.headers["traceparent"] = trace_context.traceparent
        return response
    except Exception as exc:
        json_log(
            level="error",
            message="http_request_failed",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            error=type(exc).__name__,
            trace_id=trace_context.trace_id,
            span_id=trace_context.span_id,
        )
        raise
    finally:
        duration_ms = (time.monotonic() - start) * 1000.0
        METRICS.observe(
            method=request.method,
            path=request.url.path,
            status=status_code,
            duration_ms=duration_ms,
        )
        json_log(
            level="info",
            message="http_request",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status=status_code,
            duration_ms=duration_ms,
            trace_id=trace_context.trace_id,
            span_id=trace_context.span_id,
        )


_rate_state: dict[str, tuple[float, int]] = {}


def _rate_limit_client(request: Request) -> str:
    authorization = request.headers.get("authorization")
    if authorization:
        digest = hashlib.sha256(authorization.encode("utf-8")).hexdigest()[:16]
        return f"auth:{digest}"
    return request.client.host if request.client else "unknown"


async def rate_limit_middleware(request: Request, call_next):
    try:
        rps = float(os.getenv("RATE_LIMIT_RPS", "10"))
    except ValueError:
        rps = 10.0
    if rps <= 0:
        return await call_next(request)

    now = time.monotonic()
    window = 1.0
    client = f"{_rate_limit_client(request)}:{request.url.path}"

    # Evict stale entries to prevent unbounded memory growth.
    # Only keep entries whose time window is still active.
    stale_keys = [k for k, (start, _) in _rate_state.items() if now - start >= window]
    for k in stale_keys:
        _rate_state.pop(k, None)

    start, count = _rate_state.get(client, (now, 0))
    if now - start >= window:
        start, count = now, 0
    count += 1
    _rate_state[client] = (start, count)

    if count > int(rps * window):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    return await call_next(request)
