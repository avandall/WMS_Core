from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
POLICY = ROOT_DIR / "deploy/kubernetes/examples/security-governance-policy.json"
SCRIPT = ROOT_DIR / "scripts/security_governance_check.py"

_SPEC = importlib.util.spec_from_file_location("security_governance_check", SCRIPT)
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)


def test_phase_s_plan_is_marked_done() -> None:
    source = (ROOT_DIR / "docs/internal_architecture_refactor_plan.md").read_text()
    phase_s = source.split("## Phase S: Security Governance and Authorization Hardening", 1)[1].split("## Suggested Order", 1)[0]

    assert "Status: DONE." in phase_s
    assert "fine-grained authorization scopes/permissions" in phase_s
    assert "secret rotation cadence" in phase_s
    assert "dependency/license scanning policy" in phase_s


def test_security_governance_policy_is_complete() -> None:
    policy = json.loads(POLICY.read_text())

    assert _MODULE.validate_policy(policy) == []
    assert policy["authorization_boundary"] == "api-gateway"
    assert policy["role_matrix"]["admin"] == ["*"]
    assert "warehouse_manager" in policy["role_matrix"]
    assert "documents" in policy["protected_workflows"]
    assert "jwt_secret_key" in policy["secret_rotation"]
    assert "failed_auth_attempts" in policy["audit_requirements"]
    assert "dependency-review-action" in policy["dependency_scanning"]["tools"]


def test_gateway_routes_enforce_document_and_admin_permissions_at_boundary() -> None:
    routes = (ROOT_DIR / "Services/api-gateway/src/api_gateway/routes.py").read_text()

    assert "Depends(require_permissions(Permission.MANAGE_USERS))" in routes
    assert "Depends(require_permissions(Permission.VIEW_WAREHOUSES))" in routes
    assert "Depends(require_permissions(Permission.MANAGE_WAREHOUSES))" in routes
    assert "Depends(require_permissions(Permission.VIEW_INVENTORY))" in routes
    assert "Depends(require_permissions(Permission.VIEW_DOCUMENTS))" in routes
    assert "Depends(require_permissions(Permission.MANAGE_DOCUMENTS))" in routes
    assert "Depends(require_permissions(Permission.DOC_POST))" in routes


def test_token_expiry_and_rotation_are_documented_and_implemented() -> None:
    auth = (ROOT_DIR / "Services/identity-service/src/app/shared/core/auth.py").read_text()
    settings = (ROOT_DIR / "Services/identity-service/src/app/shared/core/settings.py").read_text()
    docs = (ROOT_DIR / "docs/security_governance.md").read_text()

    assert '"exp": expire' in auth
    assert "jwt.decode(token, settings.secret_key" in auth
    assert "access_token_expire_minutes: int = 60" in settings
    assert "refresh_token_expire_minutes: int = 7 * 24 * 60" in settings
    assert "Rotate JWT `SECRET_KEY`" in docs
    assert "rolling `identity-service` and API Gateway together" in docs


def test_audit_requirements_match_audit_model_fields() -> None:
    policy = json.loads(POLICY.read_text())
    audit_model = (ROOT_DIR / "Services/audit-service/src/app/modules/audit/infrastructure/models/audit_event.py").read_text()
    docs = (ROOT_DIR / "docs/security_governance.md").read_text()

    for field in policy["audit_requirements"]["required_fields"]:
        assert field in audit_model or field in docs
    assert "privileged operations" in docs
    assert "failed auth attempts" in docs
    assert "manual inventory adjustments" in docs


def test_release_gates_include_security_and_dependency_scanning() -> None:
    workflow = (ROOT_DIR / ".github/workflows/release-gates.yml").read_text()
    release_ops = (ROOT_DIR / "docs/release_ops.md").read_text()

    assert "scripts/security_governance_check.py" in workflow
    assert "actions/dependency-review-action" in workflow
    assert "anchore/sbom-action" in workflow
    assert "aquasecurity/trivy-action" in workflow
    assert "security governance policy validation" in release_ops
    assert "dependency review on pull requests" in release_ops
