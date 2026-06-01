from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SERVICE_GRPC_SERVERS = [
    "Services/ai-service/src/ai_service/grpc_server.py",
    "Services/audit-service/src/audit_service/grpc_server.py",
    "Services/customer-service/src/customer_service/grpc_server.py",
    "Services/documents-service/src/documents_service/grpc_server.py",
    "Services/identity-service/src/identity_service/grpc_server.py",
    "Services/inventory-service/src/inventory_service/grpc_server.py",
    "Services/product-service/src/product_service/grpc_server.py",
    "Services/reporting-service/src/reporting_service/grpc_server.py",
    "Services/warehouse-service/src/warehouse_service/grpc_server.py",
]


def _compose_config() -> dict:
    result = subprocess.run(
        ["docker", "compose", "config", "--format", "json"],
        cwd=ROOT_DIR,
        env={
            **os.environ,
            "SECRET_KEY": "wms-local-dev-secret",
            "GRPC_TLS_ENABLED": "0",
            "GRPC_TLS_CERT_FILE": "",
            "GRPC_TLS_KEY_FILE": "",
            "GRPC_TLS_CLIENT_CA_FILE": "",
            "GRPC_CLIENT_TLS_ENABLED": "0",
            "GRPC_CLIENT_ROOT_CERT_FILE": "",
            "GRPC_CLIENT_CERT_FILE": "",
            "GRPC_CLIENT_KEY_FILE": "",
            "CORS_ORIGINS": "http://localhost:3000,http://localhost:8000",
            "CORS_ALLOW_CREDENTIALS": "0",
            "MAX_REQUEST_BODY_BYTES": "1048576",
            "RATE_LIMIT_RPS": "10",
        },
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_gateway_cors_and_security_headers_are_hardened() -> None:
    app_source = (ROOT_DIR / "Services/api-gateway/src/api_gateway/app.py").read_text()
    middleware_source = (ROOT_DIR / "Services/api-gateway/src/api_gateway/middleware.py").read_text()

    assert 'allow_origins=["*"]' not in app_source
    assert "CORS_ORIGINS" in app_source
    assert "CORS_ALLOW_CREDENTIALS" in app_source
    assert "expose_headers" in app_source
    assert "X-Content-Type-Options" in middleware_source
    assert "X-Frame-Options" in middleware_source
    assert "MAX_REQUEST_BODY_BYTES" in middleware_source


def test_compose_exposes_security_configuration() -> None:
    services = _compose_config()["services"]
    gateway_env = services["api-gateway"]["environment"]
    customer_env = services["customer-service"]["environment"]

    assert gateway_env["SECRET_KEY"]
    assert "SECRET_KEY: ${SECRET_KEY:-wms-local-dev-secret}" in (ROOT_DIR / "docker-compose.yml").read_text()
    assert gateway_env["GRPC_CLIENT_TLS_ENABLED"] == "0"
    assert customer_env["GRPC_TLS_ENABLED"] == "0"
    assert customer_env["GRPC_TLS_CLIENT_CA_FILE"] == ""
    assert gateway_env["GRPC_CLIENT_CERT_FILE"] == ""
    assert gateway_env["GRPC_CLIENT_KEY_FILE"] == ""
    assert gateway_env["CORS_ORIGINS"] == "http://localhost:3000,http://localhost:8000"
    assert gateway_env["CORS_ALLOW_CREDENTIALS"] == "0"
    assert gateway_env["MAX_REQUEST_BODY_BYTES"] == "1048576"
    assert gateway_env["RATE_LIMIT_RPS"] == "10"


def test_grpc_services_use_configurable_tls_ports() -> None:
    for relative_path in SERVICE_GRPC_SERVERS:
        source = (ROOT_DIR / relative_path).read_text()
        assert "add_configured_grpc_port" in source, relative_path
        assert "server.add_insecure_port" not in source, relative_path

    shared_source = (ROOT_DIR / "Libraries/shared-utils/src/shared_utils/security/grpc.py").read_text()
    assert "grpc.ssl_server_credentials" in shared_source
    assert "GRPC_TLS_CERT_FILE" in shared_source
    assert "GRPC_TLS_KEY_FILE" in shared_source
    assert "GRPC_TLS_CLIENT_CA_FILE" in shared_source
    assert "require_client_auth=client_ca is not None" in shared_source


def test_grpc_clients_can_use_secure_channels() -> None:
    gateway_source = (ROOT_DIR / "Services/api-gateway/src/api_gateway/grpc_security.py").read_text()
    shared_source = (ROOT_DIR / "Libraries/shared-utils/src/shared_utils/security/grpc.py").read_text()

    assert "GRPC_CLIENT_TLS_ENABLED" in gateway_source
    assert "grpc.secure_channel" in gateway_source
    assert "GRPC_CLIENT_ROOT_CERT_FILE" in gateway_source
    assert "GRPC_CLIENT_CERT_FILE" in gateway_source
    assert "GRPC_CLIENT_KEY_FILE" in gateway_source
    assert "grpc.secure_channel" in shared_source
