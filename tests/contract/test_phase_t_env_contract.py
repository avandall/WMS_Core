from __future__ import annotations

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]

SERVICE_ENV = {
    "api-gateway": {
        "required": {
            "IDENTITY_GRPC_ADDR",
            "CUSTOMER_GRPC_ADDR",
            "PRODUCT_GRPC_ADDR",
            "WAREHOUSE_GRPC_ADDR",
            "INVENTORY_GRPC_ADDR",
            "DOCUMENTS_GRPC_ADDR",
            "AUDIT_GRPC_ADDR",
            "REPORTING_GRPC_ADDR",
            "CORS_ORIGINS",
            "RATE_LIMIT_RPS",
        },
        "forbidden": {
            "DATABASE_URL",
            "INIT_DB_TABLES",
            "SECRET_KEY",
            "DEBUG",
            "TITLE",
            "VERSION",
            "DESCRIPTION",
            "HOST",
            "PORT",
            "API_KEY_HEADER",
        },
    },
    "identity-service": {"database_url": "sqlite:////tmp/wms-identity.db", "tables": "users"},
    "customer-service": {"database_url": "sqlite:////tmp/wms-customer.db", "tables": "customers"},
    "product-service": {"database_url": "sqlite:////tmp/wms-product.db", "tables": "products"},
    "warehouse-service": {"database_url": "sqlite:////tmp/wms-warehouse.db", "tables": "warehouses,positions"},
    "inventory-service": {
        "database_url": "sqlite:////tmp/wms-inventory.db",
        "tables": "inventory,warehouse_inventory,inventory_movement_ledger",
    },
    "documents-service": {"database_url": "sqlite:////tmp/wms-documents.db", "tables": "documents,document_items"},
    "audit-service": {"database_url": "sqlite:////tmp/wms-audit.db", "tables": "audit_events"},
    "reporting-service": {
        "database_url": "sqlite:////tmp/wms-reporting.db",
        "tables": "reporting_read_model_events,inventory_summary,document_summary,sales_summary,warehouse_activity_summary",
    },
}

DATASTORE_RUNTIME_KEYS = {
    "DB_POOL_SIZE",
    "DB_MAX_OVERFLOW",
    "DB_POOL_TIMEOUT",
    "DB_POOL_RECYCLE",
    "DEBUG",
    "JWT_ALGORITHM",
}

IDENTITY_RUNTIME_KEYS = {
    "TESTING",
    "RATE_LIMIT_PER_MINUTE",
    "ACCESS_TOKEN_EXPIRE_MINUTES",
    "REFRESH_TOKEN_EXPIRE_MINUTES",
}

STALE_TEMPLATE_KEYS = {
    "TEST_DATABASE_URL",
    "TITLE",
    "VERSION",
    "DESCRIPTION",
    "HOST",
    "PORT",
    "API_KEY_HEADER",
    "CORS_ORIGINS",
    "CORS_ALLOW_CREDENTIALS",
    "CORS_ALLOW_METHODS",
    "CORS_ALLOW_HEADERS",
}


def _parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        values[key] = value
    return values


def test_phase_t_plan_documents_service_env_templates() -> None:
    source = (ROOT_DIR / "docs/internal_architecture_refactor_plan.md").read_text()
    phase_t = source.split("## Phase T: Service Environment Templates", 1)[1].split("## Suggested Order", 1)[0]

    assert "Status: DONE." in phase_t
    assert "per-service `.env.example`" in phase_t
    assert "monolith" in phase_t
    assert "tracked AI templates out of scope" in phase_t


def test_non_ai_active_services_have_tracked_env_examples() -> None:
    for service in SERVICE_ENV:
        path = ROOT_DIR / "Services" / service / ".env.example"
        assert path.exists(), path
        source = path.read_text()
        assert "replace-with-local-dev-secret" in source or service == "api-gateway"
        assert "wms-monolith" not in source

    assert not (ROOT_DIR / "Services/ai-service/.env.example").exists()


def test_env_examples_match_compose_datastore_ownership() -> None:
    for service, expected in SERVICE_ENV.items():
        values = _parse_env(ROOT_DIR / "Services" / service / ".env.example")
        if service == "api-gateway":
            assert expected["required"].issubset(values)
            assert not expected["forbidden"] & set(values)
            continue
        assert values["DATABASE_URL"] == expected["database_url"]
        assert values["INIT_DB_TABLES"] == expected["tables"]
        assert values["LOCAL_DB_BOOTSTRAP_ENABLED"] == "1"
        assert values["SECRET_KEY"] == "replace-with-local-dev-secret"


def test_env_examples_cover_shared_runtime_knobs_without_real_secrets() -> None:
    for service in SERVICE_ENV:
        values = _parse_env(ROOT_DIR / "Services" / service / ".env.example")
        assert values["PYTHONUNBUFFERED"] == "1"
        assert values["OTEL_TRACES_EXPORTER"] == "none"
        assert values["LOG_FORMAT"] == "json"
        assert values["GRPC_TLS_ENABLED" if service != "api-gateway" else "GRPC_CLIENT_TLS_ENABLED"] == "0"
        assert "your-secret-key-here" not in values.values()


def test_datastore_env_examples_only_cover_runtime_settings() -> None:
    for service in SERVICE_ENV:
        if service == "api-gateway":
            continue
        values = _parse_env(ROOT_DIR / "Services" / service / ".env.example")
        assert DATASTORE_RUNTIME_KEYS.issubset(values)
        assert values["DB_POOL_SIZE"] == "50"
        assert values["DB_MAX_OVERFLOW"] == "30"
        assert values["DB_POOL_TIMEOUT"] == "5"
        assert values["DB_POOL_RECYCLE"] == "1800"
        assert values["JWT_ALGORITHM"] == "HS256"
        assert not STALE_TEMPLATE_KEYS & set(values)
        if service == "identity-service":
            assert IDENTITY_RUNTIME_KEYS.issubset(values)
            assert values["RATE_LIMIT_PER_MINUTE"] == "300"
        else:
            assert not IDENTITY_RUNTIME_KEYS & set(values)


def test_env_configuration_doc_lists_scope_and_rules() -> None:
    source = (ROOT_DIR / "docs/env_configuration.md").read_text()

    assert "Services/api-gateway/.env.example" in source
    assert "Services/reporting-service/.env.example" in source
    assert "Services/wms-monolith/" in source
    assert "Services/ai-service/" in source
    assert "Commit only `.env.example` templates" in source
    assert "Services/ai-service/.env" in source
    assert "Production deployment must keep runtime table bootstrap disabled" in source
