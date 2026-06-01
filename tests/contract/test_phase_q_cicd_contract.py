from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT_DIR / ".github/workflows/release-gates.yml"
SCRIPT = ROOT_DIR / "scripts/release_artifact.py"

_SPEC = importlib.util.spec_from_file_location("release_artifact", SCRIPT)
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)


def test_phase_q_plan_is_marked_done() -> None:
    source = (ROOT_DIR / "docs/internal_architecture_refactor_plan.md").read_text()
    phase_q = source.split("## Phase Q: CI/CD Release Enforcement", 1)[1].split("## Phase R:", 1)[0]

    assert "Status: DONE." in phase_q
    assert "Contract tests, gateway E2E smoke, compose config validation" in phase_q
    assert "release artifact" in phase_q


def test_release_gates_workflow_blocks_drift_and_smoke_failures() -> None:
    source = WORKFLOW.read_text()

    assert "Contract tests" in source
    assert "pytest -q tests/contract" in source
    assert "Docker Compose config" in source
    assert "docker compose config --quiet" in source
    assert "Kustomize render" in source
    assert "kubectl kustomize deploy/kubernetes/base" in source
    assert "Generated proto drift" in source
    assert "scripts/gen_protos.py" in source
    assert "git diff --exit-code" in source
    assert "Gateway contract and E2E smoke" in source
    assert "tests/e2e/run_gateway_stack_tests.sh" in source
    assert "Production cutover dry-run" in source


def test_release_candidate_build_scan_and_ai_opt_in_are_enforced() -> None:
    source = WORKFLOW.read_text()

    assert "release-candidate-build-scan" in source
    assert "docker compose build api-gateway identity-service customer-service product-service warehouse-service inventory-service documents-service audit-service reporting-service" in source
    assert "docker compose" in source
    assert "--profile ai" in source
    assert "build ai-service" in source
    assert "github.event.inputs.run_ai_image == 'true'" in source
    assert "anchore/sbom-action" in source
    assert "aquasecurity/trivy-action" in source
    assert "scripts/release_artifact.py" in source
    assert "release-artifact.json" in source


def test_release_artifact_contains_images_migrations_gates_and_rollback() -> None:
    manifest = _MODULE.build_manifest("test-release")

    assert manifest["release_version"] == "test-release"
    assert manifest["runtime_images"]["api-gateway"] == "wms/api-gateway:test-release"
    assert "ai-service" not in manifest["runtime_images"]
    assert manifest["ai_image"] == "wms/ai-service:test-release"
    assert manifest["ai_opt_in"] is True
    assert manifest["migration_commands"]["documents-service"] == "documents-migrate"
    assert "generated proto drift" in manifest["required_gates"]
    assert "SBOM" in manifest["required_gates"]
    assert "vulnerability scan" in manifest["required_gates"]
    assert "database snapshot identifiers" in manifest["rollback"]["requires"]


def test_release_docs_reference_artifact_and_ci_enforcement() -> None:
    release_ops = (ROOT_DIR / "docs/release_ops.md").read_text()
    artifact_doc = (ROOT_DIR / "docs/release_artifact.md").read_text()

    assert "CI/CD Release Enforcement" in release_ops
    assert "release-artifact.json" in release_ops
    assert "scripts/release_artifact.py" in artifact_doc
    assert "service-owned migration commands" in artifact_doc
