from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest, urlopen

from fastapi import HTTPException, Request, Response, status


@dataclass(slots=True)
class ProxiedResponse:
    status_code: int
    headers: Mapping[str, str]
    body: bytes


def _proxy_sync(url: str, *, method: str, headers: dict[str, str], body: bytes) -> ProxiedResponse:
    req = UrlRequest(url, data=body if body else None, method=method, headers=headers)
    try:
        with urlopen(req, timeout=10) as resp:
            return ProxiedResponse(
                status_code=getattr(resp, "status", 200),
                headers=dict(resp.headers.items()),
                body=resp.read(),
            )
    except HTTPError as exc:
        return ProxiedResponse(
            status_code=exc.code,
            headers=dict(getattr(exc, "headers", {}).items()),
            body=exc.read() if hasattr(exc, "read") else b"",
        )
    except URLError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Upstream service unavailable: {exc}",
        ) from exc


async def proxy_request(request: Request, *, base_url: str) -> Response:
    base = base_url.rstrip("/")
    url = f"{base}{request.url.path}"
    if request.url.query:
        url = f"{url}?{request.url.query}"

    body = await request.body()
    headers: dict[str, str] = {}
    for key in ("authorization", "content-type", "accept"):
        if key in request.headers:
            headers[key.title()] = request.headers[key]

    proxied = await asyncio.to_thread(
        _proxy_sync,
        url,
        method=request.method,
        headers=headers,
        body=body,
    )
    content_type = proxied.headers.get("Content-Type")
    return Response(content=proxied.body, status_code=proxied.status_code, media_type=content_type)

