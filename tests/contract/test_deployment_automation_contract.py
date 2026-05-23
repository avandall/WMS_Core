from __future__ import annotations

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
DEPLOY_DIR = ROOT_DIR / "deploy/kubernetes"
BASE_DIR = DEPLOY_DIR / "base"
EXAMPLES_DIR = DEPLOY_DIR / "examples"

ACTIVE_SERVICES = [
    "api-gateway",
    "identity-service",
    "customer-service",
    "product-service",
    "warehouse-service",
    "inventory-service",
    "documents-service",
    "audit-service",
    "reporting-service",
]


def _read(relative_path: str) -> str:
    return (ROOT_DIR / relative_path).read_text()


def test_kubernetes_base_is_present_and_deployable() -> None:
    expected_files = [
        "namespace.yaml",
        "configmap.yaml",
        "secrets.example.yaml",
        "event-bus.yaml",
        "otel-collector.yaml",
        "services.yaml",
    ]
    kustomization = (BASE_DIR / "kustomization.yaml").read_text()

    for filename in expected_files:
        assert (BASE_DIR / filename).exists()
        assert f"- {filename}" in kustomization

    assert (DEPLOY_DIR / "README.md").exists()
    assert "kubectl apply -k deploy/kubernetes/base" in (DEPLOY_DIR / "README.md").read_text()
    assert "kubectl kustomize deploy/kubernetes/base" in (DEPLOY_DIR / "README.md").read_text()
    assert "kubectl apply -k deploy/kubernetes/base --dry-run=server" in (
        DEPLOY_DIR / "README.md"
    ).read_text()


def test_active_services_have_release_images_and_probes() -> None:
    services_manifest = (BASE_DIR / "services.yaml").read_text()

    for service in ACTIVE_SERVICES:
        assert f"name: {service}" in services_manifest
        assert f"image: wms/{service}:RELEASE_VERSION" in services_manifest

    assert "ai-service" not in services_manifest
    assert "wms-monolith" not in services_manifest
    assert "readinessProbe:" in services_manifest
    assert "livenessProbe:" in services_manifest
    assert "resources:" in services_manifest
    assert "secretName: wms-grpc-mtls" in services_manifest


def test_secret_manager_and_grpc_tls_contract_are_wired() -> None:
    configmap = (BASE_DIR / "configmap.yaml").read_text()
    secrets = (BASE_DIR / "secrets.example.yaml").read_text()

    assert "GRPC_TLS_ENABLED: \"1\"" in configmap
    assert "GRPC_CLIENT_TLS_ENABLED: \"1\"" in configmap
    assert "/etc/wms/grpc/tls.crt" in configmap
    assert "wms-grpc-mtls" in secrets
    assert "replace-with-secret-manager-value" in secrets
    assert "replace-with-service-owned-database-url" in secrets
    assert "sqlite:" not in secrets


def test_migration_jobs_exist_per_service_without_ai_or_monolith() -> None:
    migration_jobs = (EXAMPLES_DIR / "migration-jobs.yaml").read_text()

    for service in ACTIVE_SERVICES:
        if service == "api-gateway":
            continue
        assert f"name: {service}-migration" in migration_jobs
        assert f"image: wms/{service}:RELEASE_VERSION" in migration_jobs

    assert "replace-with-" in migration_jobs
    assert "ai-service" not in migration_jobs
    assert "wms-monolith" not in migration_jobs


def test_observability_slo_and_release_gates_are_documented() -> None:
    otel = (BASE_DIR / "otel-collector.yaml").read_text()
    slo_alerts = (EXAMPLES_DIR / "slo-alerts.yaml").read_text()
    checks = (EXAMPLES_DIR / "load-chaos-checks.md").read_text()
    release_ops = _read("docs/release_ops.md")
    roadmap = _read("docs/roadmap.md")

    assert "kind: Deployment" in otel
    assert "otel/opentelemetry-collector-contrib" in otel
    assert "PrometheusRule" in slo_alerts
    assert "WmsGatewayHighErrorRate" in slo_alerts
    assert "k6 run load/customer-flow.js" in checks
    assert "deploy/kubernetes/base" in release_ops
    assert "Phase 17: Production Deployment Automation — DONE" in roadmap
