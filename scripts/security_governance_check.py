from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_ROLES = {"admin", "user", "sales", "warehouse", "warehouse_manager", "accountant"}
REQUIRED_WORKFLOWS = {"admin_only", "warehouse", "inventory", "documents"}
REQUIRED_ROTATION_KEYS = {"jwt_secret_key", "grpc_mtls_certificates", "database_credentials", "external_provider_keys"}
REQUIRED_AUDIT_FIELDS = {"event_id", "request_id", "user_id", "action", "entity_type", "entity_id", "warehouse_id", "payload", "created_at"}
REQUIRED_SCAN_TOOLS = {"dependency-review-action", "trivy", "sbom-action"}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the WMS security governance policy.")
    parser.add_argument("--policy", required=True, help="Path to security-governance-policy.json")
    return parser.parse_args()


def load_policy(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def validate_policy(policy: dict[str, Any]) -> list[str]:
    failures: list[str] = []

    if policy.get("authorization_boundary") != "api-gateway":
        failures.append("authorization_boundary must be api-gateway")

    role_matrix = policy.get("role_matrix", {})
    missing_roles = REQUIRED_ROLES - set(role_matrix)
    if missing_roles:
        failures.append(f"missing role_matrix roles: {sorted(missing_roles)}")
    if role_matrix.get("admin") != ["*"]:
        failures.append("admin role must explicitly have wildcard permissions")

    protected_workflows = policy.get("protected_workflows", {})
    missing_workflows = REQUIRED_WORKFLOWS - set(protected_workflows)
    if missing_workflows:
        failures.append(f"missing protected workflows: {sorted(missing_workflows)}")

    token_policy = policy.get("token_policy", {})
    if token_policy.get("issuer") != "identity-service":
        failures.append("token_policy.issuer must be identity-service")
    if not token_policy.get("access_token_expire_minutes"):
        failures.append("token_policy.access_token_expire_minutes is required")
    if "SECRET_KEY" not in token_policy.get("rotation", ""):
        failures.append("token_policy.rotation must mention SECRET_KEY")

    rotation = policy.get("secret_rotation", {})
    missing_rotation = REQUIRED_ROTATION_KEYS - set(rotation)
    if missing_rotation:
        failures.append(f"missing secret_rotation entries: {sorted(missing_rotation)}")
    for name, spec in rotation.items():
        for key in ("cadence", "owner", "rollback"):
            if not spec.get(key):
                failures.append(f"secret_rotation.{name}.{key} is required")

    audit = policy.get("audit_requirements", {})
    fields = set(audit.get("required_fields", []))
    missing_fields = REQUIRED_AUDIT_FIELDS - fields
    if missing_fields:
        failures.append(f"missing audit required fields: {sorted(missing_fields)}")
    for key in ("privileged_operations", "failed_auth_attempts", "data_export", "manual_inventory_adjustments"):
        if not audit.get(key):
            failures.append(f"audit_requirements.{key} is required")

    dependency_scanning = policy.get("dependency_scanning", {})
    tools = set(dependency_scanning.get("tools", []))
    missing_tools = REQUIRED_SCAN_TOOLS - tools
    if missing_tools:
        failures.append(f"missing dependency scanning tools: {sorted(missing_tools)}")
    if not dependency_scanning.get("remediation_sla"):
        failures.append("dependency_scanning.remediation_sla is required")
    if not dependency_scanning.get("owners"):
        failures.append("dependency_scanning.owners is required")

    return failures


def main() -> None:
    args = _parse_args()
    failures = validate_policy(load_policy(Path(args.policy)))
    result = {"status": "failed" if failures else "passed", "failures": failures}
    print(json.dumps(result, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
