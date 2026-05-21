from __future__ import annotations

import json
import os
import re
import secrets
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any


TRACEPARENT_RE = re.compile(
    r"^(?P<version>[0-9a-f]{2})-(?P<trace_id>[0-9a-f]{32})-(?P<span_id>[0-9a-f]{16})-(?P<flags>[0-9a-f]{2})$"
)


@dataclass(frozen=True, slots=True)
class TraceContext:
    trace_id: str
    span_id: str
    sampled: bool = True

    @property
    def traceparent(self) -> str:
        flags = "01" if self.sampled else "00"
        return f"00-{self.trace_id}-{self.span_id}-{flags}"


def _token_hex(bytes_count: int) -> str:
    value = "0" * (bytes_count * 2)
    while set(value) == {"0"}:
        value = secrets.token_hex(bytes_count)
    return value


def parse_traceparent(traceparent: str | None) -> TraceContext | None:
    if not traceparent:
        return None
    match = TRACEPARENT_RE.match(traceparent.strip().lower())
    if not match:
        return None
    trace_id = match.group("trace_id")
    span_id = match.group("span_id")
    if set(trace_id) == {"0"} or set(span_id) == {"0"}:
        return None
    return TraceContext(
        trace_id=trace_id,
        span_id=span_id,
        sampled=bool(int(match.group("flags"), 16) & 1),
    )


def child_trace_context(parent: TraceContext | None = None) -> TraceContext:
    return TraceContext(
        trace_id=parent.trace_id if parent else _token_hex(16),
        span_id=_token_hex(8),
        sampled=parent.sampled if parent else True,
    )


@dataclass(slots=True)
class Metrics:
    requests_total: dict[str, int]
    requests_by_path: dict[str, int]
    request_duration_ms_sum: dict[str, float]

    def __init__(self) -> None:
        self.requests_total = defaultdict(int)
        self.requests_by_path = defaultdict(int)
        self.request_duration_ms_sum = defaultdict(float)

    def observe(self, *, method: str, path: str, status: int, duration_ms: float) -> None:
        key = f"{method} {status}"
        self.requests_total[key] += 1
        self.requests_by_path[path] += 1
        self.request_duration_ms_sum[path] += float(duration_ms)

    def render_prometheus(self) -> str:
        lines: list[str] = []
        lines.append("# TYPE api_gateway_requests_total counter")
        for k, v in sorted(self.requests_total.items()):
            method, status = k.split(" ", 1)
            lines.append(f'api_gateway_requests_total{{method="{method}",status="{status}"}} {v}')

        lines.append("# TYPE api_gateway_requests_by_path_total counter")
        for path, v in sorted(self.requests_by_path.items()):
            lines.append(f'api_gateway_requests_by_path_total{{path="{path}"}} {v}')

        lines.append("# TYPE api_gateway_request_duration_ms_sum counter")
        for path, v in sorted(self.request_duration_ms_sum.items()):
            lines.append(f'api_gateway_request_duration_ms_sum{{path="{path}"}} {v:.3f}')

        return "\n".join(lines) + "\n"


METRICS = Metrics()


def json_log(*, level: str, message: str, request_id: str | None = None, **fields: Any) -> None:
    if os.getenv("LOG_FORMAT", "json") != "json":
        return
    record = {"ts": time.time(), "level": level, "msg": message}
    if request_id:
        record["request_id"] = request_id
    record.update(fields)
    print(json.dumps(record, ensure_ascii=False, default=str))
