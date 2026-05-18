from __future__ import annotations

import json
import os
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any


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

