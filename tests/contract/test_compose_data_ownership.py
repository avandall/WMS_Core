from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]


def _compose_config(*args: str) -> dict:
    result = subprocess.run(
        ["docker", "compose", *args, "config", "--format", "json"],
        cwd=ROOT_DIR,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_default_compose_uses_service_owned_datastore_urls() -> None:
    config = _compose_config()
    services = config["services"]

    assert "DATABASE_URL" not in services["api-gateway"]["environment"]
    assert "ai-service" not in services

    expected_databases = {
        "identity-service": "sqlite:////tmp/wms-identity.db",
        "customer-service": "sqlite:////tmp/wms-customer.db",
        "product-service": "sqlite:////tmp/wms-product.db",
        "warehouse-service": "sqlite:////tmp/wms-warehouse.db",
        "inventory-service": "sqlite:////tmp/wms-inventory.db",
        "documents-service": "sqlite:////tmp/wms-documents.db",
        "audit-service": "sqlite:////tmp/wms-audit.db",
        "reporting-service": "sqlite:////tmp/wms-reporting.db",
    }

    actual_databases = {
        service: services[service]["environment"]["DATABASE_URL"]
        for service in expected_databases
    }
    assert actual_databases == expected_databases
    assert len(set(actual_databases.values())) == len(actual_databases)

    assert services["audit-service"]["environment"]["INIT_DB_TABLES"] == "audit_events"


def test_ai_profile_has_its_own_datastore_configuration() -> None:
    config = _compose_config("--profile", "ai")
    ai_environment = config["services"]["ai-service"]["environment"]

    assert ai_environment["DB_CONNECTION_STRING"] == "sqlite:////tmp/wms-ai.db"
    assert ai_environment["VECTOR_DB_PATH"] == "/tmp/wms-ai-vector-db"
