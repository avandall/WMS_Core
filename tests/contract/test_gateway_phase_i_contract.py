from __future__ import annotations

import ast
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
GATEWAY = ROOT_DIR / "Services/api-gateway/src/api_gateway"


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return modules


def test_gateway_does_not_import_service_domain_application_or_infrastructure() -> None:
    failures: list[str] = []
    forbidden_parts = {"app.modules", ".domain.", ".application.", ".infrastructure."}

    for path in sorted(GATEWAY.rglob("*.py")):
        if "gen" in path.parts or "__pycache__" in path.parts:
            continue
        for module in _imports(path):
            if module.startswith("app.modules") or any(part in module for part in forbidden_parts):
                failures.append(f"{path.relative_to(ROOT_DIR)} imports {module}")

    assert failures == []


def test_gateway_routes_use_central_grpc_call_and_presenters() -> None:
    routes = (GATEWAY / "routes.py").read_text()
    presenters = (GATEWAY / "presenters.py").read_text()

    assert "def _grpc_call" in routes
    assert "raise grpc_http_exception" in routes
    assert "customer_to_dict" in routes
    assert "product_to_dict" in routes
    assert "warehouse_to_dict" in routes
    assert "document_to_dict" in routes
    assert "audit_event_to_dict" in routes
    assert "def customer_to_dict" in presenters
    assert "def parse_json" in presenters
    assert "_try_json" not in routes


def test_gateway_keeps_transport_concerns_but_no_wms_repositories() -> None:
    gateway_source = "\n".join(
        path.read_text()
        for path in sorted(GATEWAY.rglob("*.py"))
        if "gen" not in path.parts and "__pycache__" not in path.parts
    )

    assert "require_permissions" in gateway_source
    assert "traceparent" in gateway_source
    assert "x-request-id" in gateway_source
    assert "grpc_http_exception" in gateway_source
    assert "Repo(" not in gateway_source
    assert "Repository" not in gateway_source
