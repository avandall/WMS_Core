from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

RUNTIME_SERVICES = [
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

MIGRATION_COMMANDS = {
    "identity-service": "identity-migrate",
    "customer-service": "customer-migrate",
    "product-service": "product-migrate",
    "warehouse-service": "warehouse-migrate",
    "inventory-service": "inventory-migrate",
    "documents-service": "documents-migrate",
    "audit-service": "audit-migrate",
    "reporting-service": "reporting-migrate",
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a release artifact manifest for the WMS stack.")
    parser.add_argument("--release-version", default="", help="Immutable release version. Defaults to git SHA.")
    parser.add_argument("--output", default="", help="Optional output JSON path.")
    return parser.parse_args()


def _git_sha() -> str:
    return subprocess.check_output(["git", "rev-parse", "--short=12", "HEAD"], cwd=ROOT, text=True).strip()


def build_manifest(release_version: str) -> dict[str, Any]:
    version = release_version or _git_sha()
    return {
        "release_version": version,
        "git_sha": _git_sha(),
        "runtime_images": {service: f"wms/{service}:{version}" for service in RUNTIME_SERVICES},
        "ai_image": f"wms/ai-service:{version}",
        "ai_opt_in": True,
        "migration_commands": MIGRATION_COMMANDS,
        "required_gates": [
            "contract tests",
            "gateway e2e smoke",
            "docker compose config",
            "kustomize render",
            "kubernetes server dry-run",
            "generated proto drift",
            "migration job ownership",
            "SBOM",
            "vulnerability scan",
            "production cutover dry-run",
        ],
        "deployment_artifacts": [
            "deploy/kubernetes/base",
            "deploy/kubernetes/examples/migration-jobs.yaml",
            "deploy/kubernetes/examples/secret-manager-external-secrets.yaml",
            "deploy/kubernetes/examples/production-cutover-manifest.example.json",
        ],
        "rollback": {
            "rule": "rollback gateway first, then downstream services in reverse rollout order",
            "requires": [
                "previous release artifact",
                "database snapshot identifiers",
                "Redis stream offsets",
                "migration command list",
            ],
        },
    }


def main() -> None:
    args = _parse_args()
    manifest = build_manifest(args.release_version)
    payload = json.dumps(manifest, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(payload + "\n")
    else:
        print(payload)


if __name__ == "__main__":
    main()
