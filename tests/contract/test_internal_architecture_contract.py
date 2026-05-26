from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
ACTIVE_SERVICE_DIRS = [
    path
    for path in sorted((ROOT_DIR / "Services").glob("*-service"))
    if path.name != "wms-monolith"
]

OWNED_MODULES = {
    "audit-service": {"audit"},
    "customer-service": {"customers"},
    "documents-service": {"documents"},
    "identity-service": {"users"},
    "inventory-service": {"inventory"},
    "product-service": {"products"},
    "reporting-service": {"reporting"},
    "warehouse-service": {"warehouses"},
}

PHASE_B_ALLOWED_NON_OWNED_MODULES = {
    "audit-service": set(),
    "customer-service": set(),
    "documents-service": {
        "audit",
        "customers",
        "inventory",
        "positions",
        "products",
        "users",
        "warehouses",
    },
    "identity-service": set(),
    "inventory-service": set(),
    "product-service": set(),
    "reporting-service": {"customers", "documents", "inventory", "products", "warehouses"},
    "warehouse-service": {"documents", "inventory", "positions", "products"},
}

OWNED_INIT_TABLES = {
    "audit-service": {"audit_events"},
    "customer-service": {"customers"},
    "documents-service": {"documents", "document_items"},
    "identity-service": {"users"},
    "inventory-service": {"inventory", "warehouse_inventory"},
    "product-service": {"products"},
    "reporting-service": {"reporting_read_model_events"},
    "warehouse-service": {"warehouses", "positions"},
}

PHASE_B_ALLOWED_NON_OWNED_INIT_TABLES = {
    "audit-service": set(),
    "customer-service": set(),
    "documents-service": {"customers", "products", "warehouses"},
    "identity-service": set(),
    "inventory-service": set(),
    "product-service": set(),
    "reporting-service": {
        "customer_purchases",
        "customers",
        "document_items",
        "documents",
        "inventory",
        "products",
        "warehouse_inventory",
        "warehouses",
    },
    "warehouse-service": {
        "inventory",
        "position_inventory",
        "products",
        "warehouse_inventory",
    },
}

DOMAIN_FORBIDDEN_IMPORT_PARTS = {
    "application",
    "infrastructure",
    "fastapi",
    "grpc",
    "redis",
    "sqlalchemy",
}

APPLICATION_FORBIDDEN_IMPORT_PARTS = {
    "fastapi",
    "grpc",
    "redis",
}


def _python_files_under(*parts: str | Path) -> list[Path]:
    base = ROOT_DIR.joinpath(*parts)
    if not base.exists():
        return []
    return [
        path
        for path in sorted(base.rglob("*.py"))
        if "__pycache__" not in path.parts
        and "gen" not in path.parts
        and "wms-monolith" not in path.parts
    ]


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return modules


def _violations(path: Path, forbidden_parts: set[str]) -> list[str]:
    violations = []
    for module in _imports(path):
        parts = set(module.split("."))
        if parts & forbidden_parts or module.endswith("_pb2") or module.endswith("_pb2_grpc"):
            violations.append(module)
    return violations


def _compose_config() -> dict:
    result = subprocess.run(
        ["docker", "compose", "config", "--format", "json"],
        cwd=ROOT_DIR,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_architecture_docs_define_active_service_patterns_and_templates() -> None:
    architecture = (ROOT_DIR / "docs/architecture.md").read_text()
    template = (ROOT_DIR / "docs/service_template.md").read_text()

    assert "Services/wms-monolith" in architecture
    assert "outside the refactor scope" in architecture

    for service in OWNED_MODULES:
        assert f"`{service}`" in architecture

    for category in [
        "BFF/API Composition Service",
        "CRUD/Application Service",
        "Tactical DDD Service",
        "Event Consumer Service",
        "Read-Model Service",
        "AI Pipeline Service",
    ]:
        assert category in template


def test_domain_layer_does_not_import_application_infrastructure_or_transport() -> None:
    failures: list[str] = []

    for service_dir in ACTIVE_SERVICE_DIRS:
        for domain_file in _python_files_under(service_dir.relative_to(ROOT_DIR), "src/app/modules"):
            if "domain" not in domain_file.parts:
                continue
            violations = _violations(domain_file, DOMAIN_FORBIDDEN_IMPORT_PARTS)
            if violations:
                failures.append(
                    f"{domain_file.relative_to(ROOT_DIR)} imports forbidden modules: {violations}"
                )

    assert failures == []


def test_application_layer_does_not_import_transport_runtime_clients() -> None:
    failures: list[str] = []

    for service_dir in ACTIVE_SERVICE_DIRS:
        module_root = service_dir / "src/app/modules"
        for app_file in sorted(module_root.glob("*/application/**/*.py")):
            if "__pycache__" in app_file.parts:
                continue
            violations = _violations(app_file, APPLICATION_FORBIDDEN_IMPORT_PARTS)
            if violations:
                failures.append(
                    f"{app_file.relative_to(ROOT_DIR)} imports forbidden modules: {violations}"
                )

    assert failures == []


def test_active_services_do_not_add_new_non_owned_modules_before_phase_b() -> None:
    failures: list[str] = []

    for service_dir in ACTIVE_SERVICE_DIRS:
        modules_root = service_dir / "src/app/modules"
        if not modules_root.exists():
            continue

        actual_modules = {
            path.name
            for path in modules_root.iterdir()
            if path.is_dir() and not path.name.startswith("__")
        }
        service = service_dir.name
        allowed_modules = OWNED_MODULES.get(service, set()) | PHASE_B_ALLOWED_NON_OWNED_MODULES.get(
            service, set()
        )
        unknown_modules = actual_modules - allowed_modules
        if unknown_modules:
            failures.append(f"{service} has unexpected modules: {sorted(unknown_modules)}")

    assert failures == []


def test_compose_does_not_add_new_non_owned_init_tables_before_phase_b() -> None:
    services = _compose_config()["services"]
    failures: list[str] = []

    for service, owned_tables in OWNED_INIT_TABLES.items():
        environment = services[service]["environment"]
        actual_tables = {
            table.strip()
            for table in environment.get("INIT_DB_TABLES", "").split(",")
            if table.strip()
        }
        allowed_tables = owned_tables | PHASE_B_ALLOWED_NON_OWNED_INIT_TABLES.get(service, set())
        unknown_tables = actual_tables - allowed_tables
        if unknown_tables:
            failures.append(f"{service} initializes unexpected tables: {sorted(unknown_tables)}")

    assert failures == []
