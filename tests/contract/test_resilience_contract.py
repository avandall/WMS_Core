from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import grpc
import pytest

from api_gateway.grpc_clients import CircuitOpenError, _circuit_state, call_idempotent


ROOT_DIR = Path(__file__).resolve().parents[2]


class RetryableRpcError(grpc.RpcError):
    def code(self) -> grpc.StatusCode:
        return grpc.StatusCode.UNAVAILABLE

    def details(self) -> str:
        return "downstream unavailable"


def _compose_config() -> dict:
    result = subprocess.run(
        ["docker", "compose", "config", "--format", "json"],
        cwd=ROOT_DIR,
        env={
            **os.environ,
            "GRPC_TIMEOUT_FAST": "5",
            "GRPC_TIMEOUT_DEFAULT": "10",
            "GRPC_TIMEOUT_SLOW": "30",
            "GRPC_TIMEOUT_AI": "60",
            "GRPC_RETRY_ATTEMPTS": "2",
            "GRPC_RETRY_BACKOFF_SECONDS": "0.05",
            "CIRCUIT_BREAKER_FAILURE_THRESHOLD": "5",
            "CIRCUIT_BREAKER_RECOVERY_SECONDS": "15",
            "AUDIT_EVENT_CONSUMER_BLOCK_MS": "5000",
            "AUDIT_EVENT_CONSUMER_BATCH_SIZE": "20",
            "AUDIT_EVENT_CONSUMER_MAX_STREAM_LENGTH": "10000",
        },
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_compose_exposes_resilience_configuration() -> None:
    services = _compose_config()["services"]
    gateway_env = services["api-gateway"]["environment"]
    audit_env = services["audit-service"]["environment"]

    assert gateway_env["GRPC_TIMEOUT_DEFAULT"] == "10"
    assert gateway_env["GRPC_RETRY_ATTEMPTS"] == "2"
    assert gateway_env["CIRCUIT_BREAKER_FAILURE_THRESHOLD"] == "5"
    assert gateway_env["CIRCUIT_BREAKER_RECOVERY_SECONDS"] == "15"
    assert audit_env["AUDIT_EVENT_CONSUMER_BATCH_SIZE"] == "20"
    assert audit_env["AUDIT_EVENT_CONSUMER_MAX_STREAM_LENGTH"] == "10000"


def test_circuit_breaker_opens_after_retryable_downstream_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    _circuit_state.clear()
    monkeypatch.setenv("GRPC_RETRY_ATTEMPTS", "1")
    monkeypatch.setenv("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "1")
    monkeypatch.setenv("CIRCUIT_BREAKER_RECOVERY_SECONDS", "60")

    def failing_call(_request, *, timeout: float, metadata=None):
        raise RetryableRpcError()

    failing_call._method = b"/wms.customer.v1.CustomerService/ListCustomers"  # type: ignore[attr-defined]

    with pytest.raises(RetryableRpcError):
        call_idempotent(failing_call, object(), timeout=0.1)

    with pytest.raises(CircuitOpenError):
        call_idempotent(failing_call, object(), timeout=0.1)


def test_resilience_docs_cover_slo_chaos_and_backpressure() -> None:
    source = (ROOT_DIR / "docs/resilience.md").read_text()

    assert "SLO Baseline" in source
    assert "Circuit Breaker" in source
    assert "Event Consumer Backpressure" in source
    assert "Failure Testing" in source


def test_audit_consumer_has_stream_backpressure_guard() -> None:
    source = (ROOT_DIR / "Services/audit-service/src/audit_service/event_consumer.py").read_text()
    redis_source = (ROOT_DIR / "Libraries/shared-utils/src/shared_utils/events/publisher.py").read_text()

    assert "AUDIT_EVENT_CONSUMER_MAX_STREAM_LENGTH" in source
    assert "def _apply_backpressure" in source
    assert "self.client.xlen(self.stream)" in source
    assert "def xlen" in redis_source
