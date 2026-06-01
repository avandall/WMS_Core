from __future__ import annotations

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (ROOT_DIR / relative_path).read_text()


def test_secret_manager_and_rotation_paths_are_documented() -> None:
    external_secrets = _read("deploy/kubernetes/examples/secret-manager-external-secrets.yaml")
    security = _read("docs/security.md")
    deploy_readme = _read("deploy/kubernetes/README.md")

    assert "kind: ExternalSecret" in external_secrets
    assert "platform-secret-store" in external_secrets
    assert "wms/production/secret-key" in external_secrets
    assert "wms/production/grpc/tls-crt" in external_secrets
    assert "wms-secrets" in external_secrets
    assert "wms-grpc-mtls" in external_secrets
    assert "gRPC mTLS" in security
    assert "JWT signing key" in security
    assert "Database credentials" in security
    assert "secret-manager-external-secrets.yaml" in deploy_readme


def test_observability_queries_cover_gateway_and_async_operations() -> None:
    queries = _read("deploy/kubernetes/examples/observability-queries.md")
    alerts = _read("deploy/kubernetes/examples/slo-alerts.yaml")
    observability = _read("docs/observability.md")

    assert "http_requests_total" in queries
    assert "http_request_duration_seconds_bucket" in queries
    assert 'redis_stream_length{stream="wms.events"}' in queries
    assert 'redis_stream_length{stream=~"wms.events.(audit|inventory|reporting|ai).dlq"}' in queries
    assert 'redis_stream_length{stream="wms.events.replay"}' in queries
    assert "WmsEventDlqDepthNonZero" in alerts
    assert "WmsReplayStreamStuck" in alerts
    assert "observability-queries.md" in observability


def test_release_gates_cover_core_flows_and_async_lag() -> None:
    checks = _read("deploy/kubernetes/examples/load-chaos-checks.md")
    release_ops = _read("docs/release_ops.md")

    assert "Auth Gate" in checks
    assert "Core Business Gates" in checks
    assert "/api/v1/customers" in checks
    assert "/api/v1/inventory" in checks
    assert "/api/v1/documents" in checks
    assert "Async lag gate" in checks
    assert "promtool query instant" in checks
    assert "Rotate JWT `SECRET_KEY`" in checks
    assert "document/inventory flow" in release_ops
    assert "async consumer lag/DLQ gates" in release_ops


def test_ai_remains_out_of_default_deployment_artifacts() -> None:
    services = _read("deploy/kubernetes/base/services.yaml")
    kustomization = _read("deploy/kubernetes/base/kustomization.yaml")
    deploy_readme = _read("deploy/kubernetes/README.md")

    assert "ai-service" not in services
    assert "ai-service" not in kustomization
    assert "explicit AI overlay" in deploy_readme


def test_phase_n_plan_is_marked_done() -> None:
    plan = _read("docs/internal_architecture_refactor_plan.md")

    assert "## Phase N: Deployment, Observability, and Security Hardening" in plan
    assert "Status: DONE." in plan
    assert "saved PromQL queries" in plan
    assert "secret-manager wiring" in plan
