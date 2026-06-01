from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from shared_utils.observability import child_trace_context, parse_traceparent


ROOT_DIR = Path(__file__).resolve().parents[2]
TRACEPARENT_RE = re.compile(r"^00-[0-9a-f]{32}-[0-9a-f]{16}-0[01]$")


def _compose_config() -> dict:
    result = subprocess.run(
        ["docker", "compose", "config", "--format", "json"],
        cwd=ROOT_DIR,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_traceparent_parser_and_child_context_keep_trace_id() -> None:
    parent = parse_traceparent("00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01")
    assert parent is not None

    child = child_trace_context(parent)
    assert child.trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert child.span_id != parent.span_id
    assert TRACEPARENT_RE.match(child.traceparent)


def test_gateway_propagates_traceparent_to_grpc_metadata() -> None:
    source = (ROOT_DIR / "Services/api-gateway/src/api_gateway/routes.py").read_text()
    auth_source = (ROOT_DIR / "Services/api-gateway/src/api_gateway/auth.py").read_text()

    assert '("traceparent", traceparent)' in source
    assert '("traceparent", traceparent)' in auth_source


def test_compose_is_otlp_ready() -> None:
    services = _compose_config()["services"]

    assert services["api-gateway"]["environment"]["OTEL_EXPORTER_OTLP_ENDPOINT"] == "http://otel-collector:4317"
    assert services["customer-service"]["environment"]["OTEL_TRACES_EXPORTER"] == "otlp"
