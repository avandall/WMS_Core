from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]

DATASTORE_SERVICES = {
    "identity-service": "identity",
    "customer-service": "customer",
    "product-service": "product",
    "warehouse-service": "warehouse",
    "inventory-service": "inventory",
    "documents-service": "documents",
    "audit-service": "audit",
    "reporting-service": "reporting",
}


def _read(relative_path: str) -> str:
    return (ROOT_DIR / relative_path).read_text()


def _compose_config(*args: str) -> dict:
    result = subprocess.run(
        ["docker", "compose", *args, "config", "--format", "json"],
        cwd=ROOT_DIR,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_datastore_services_expose_migration_and_fixture_commands() -> None:
    for service, command_prefix in DATASTORE_SERVICES.items():
        pyproject = _read(f"Services/{service}/pyproject.toml")
        package = f"{command_prefix}_service" if command_prefix != "documents" else "documents_service"
        assert f'{command_prefix}-migrate = "{package}.bootstrap:migrate"' in pyproject
        assert f'{command_prefix}-fixtures = "{package}.bootstrap:fixtures"' in pyproject
        bootstrap = _read(f"Services/{service}/src/{package}/bootstrap.py")
        assert "sys.path.insert" in bootstrap
        assert "sys.path.remove" in bootstrap
        assert f'migrate_service("{command_prefix}")' in bootstrap

    bootstrap = _read("Libraries/shared-utils/src/shared_utils/service_bootstrap.py")
    assert "SERVICE_MIGRATION_MODE" in bootstrap
    assert "database.init_db()" in bootstrap
    assert "no default fixtures to load" in bootstrap


def test_runtime_table_bootstrap_is_local_only() -> None:
    compose = _compose_config()

    for service in DATASTORE_SERVICES:
        assert compose["services"][service]["environment"]["LOCAL_DB_BOOTSTRAP_ENABLED"] == "1"

    services_manifest = _read("deploy/kubernetes/base/services.yaml")
    assert "LOCAL_DB_BOOTSTRAP_ENABLED" not in services_manifest

    for service in DATASTORE_SERVICES:
        source = _read(f"Services/{service}/src/app/shared/core/database.py")
        assert "LOCAL_DB_BOOTSTRAP_ENABLED" in source
        assert "SERVICE_MIGRATION_MODE" in source
        assert "Skipping runtime table bootstrap" in source


def test_kubernetes_migration_jobs_use_service_owned_commands() -> None:
    migration_jobs = _read("deploy/kubernetes/examples/migration-jobs.yaml")

    assert "replace-with-" not in migration_jobs
    assert "wms-monolith" not in migration_jobs
    assert "ai-service" not in migration_jobs

    for service, command_prefix in DATASTORE_SERVICES.items():
        assert f"name: {service}-migration" in migration_jobs
        assert f"image: wms/{service}:RELEASE_VERSION" in migration_jobs
        assert f'command: ["{command_prefix}-migrate"]' in migration_jobs


def test_phase_l_docs_record_remaining_fixture_and_migration_boundary() -> None:
    plan = _read("docs/internal_architecture_refactor_plan.md")
    release_ops = _read("docs/release_ops.md")
    deploy_readme = _read("deploy/kubernetes/README.md")
    monolith = _read("docs/monolith_retirement.md")

    assert "## Phase L: Production Migration and Fixture Ownership" in plan
    assert "Status: DONE." in plan
    assert "`*-migrate`" in release_ops
    assert "LOCAL_DB_BOOTSTRAP_ENABLED=1" in release_ops
    assert "`*-migrate` command" in deploy_readme
    assert "identity-fixtures" in monolith
