from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol

from ai_service.pipeline.templates import QueryTemplate


@dataclass(frozen=True, slots=True)
class BackendQueryResponse:
    success: bool
    payload: dict[str, Any]
    error: str = ""


class BackendQueryClient(Protocol):
    def execute(self, *, template: QueryTemplate) -> BackendQueryResponse: ...


class TemplateBackendQueryClient:
    """
    Backend query boundary for structured data requests.

    It accepts normalized key-value templates and returns a structured payload.
    A real gRPC/HTTP backend adapter can replace this class without changing the
    router or template extractor.
    """

    def execute(self, *, template: QueryTemplate) -> BackendQueryResponse:
        return BackendQueryResponse(
            success=True,
            payload={
                "status": "template_prepared",
                "template": template.to_dict(),
            },
        )


class HttpBackendQueryClient:
    """POSTs query templates to a backend endpoint that owns operational data access."""

    def __init__(self, endpoint: str, auth_token: str | None = None, timeout_seconds: float = 10.0):
        self.endpoint = endpoint
        self.auth_token = auth_token
        self.timeout_seconds = timeout_seconds

    def execute(self, *, template: QueryTemplate) -> BackendQueryResponse:
        body = json.dumps({"template": template.to_dict()}, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=body,
            headers=self._headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8") or "{}")
            return BackendQueryResponse(success=True, payload=payload)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            return BackendQueryResponse(success=False, payload={}, error=str(exc))

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers


def default_backend_query_client() -> BackendQueryClient:
    endpoint = os.getenv("AI_BACKEND_QUERY_URL", "").strip()
    if endpoint:
        return HttpBackendQueryClient(
            endpoint=endpoint,
            auth_token=os.getenv("AI_BACKEND_QUERY_TOKEN") or None,
            timeout_seconds=float(os.getenv("AI_BACKEND_QUERY_TIMEOUT", "10")),
        )
    return TemplateBackendQueryClient()


def render_backend_response(response: BackendQueryResponse) -> str:
    return json.dumps(response.payload, ensure_ascii=False, sort_keys=True)
