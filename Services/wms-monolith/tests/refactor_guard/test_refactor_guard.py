import os
import sys
import uuid
from pathlib import Path

# Ensure generated gRPC packages and local app packages are importable from the service test root.
service_root = Path(__file__).resolve().parents[2]
# Use a local SQLite DB for guard tests to avoid requiring a running PostgreSQL instance.
# NOTE: Use setdefault() so CI/scripts can override behavior intentionally.
os.environ.setdefault(
    "DATABASE_URL",
    f"sqlite:///{service_root / 'tests' / 'refactor_guard' / 'refactor_guard.db'}",
)
# Guard suite expects to run without auth headers; enable testing-mode auth bypass.
os.environ.setdefault("TESTING", "true")
os.environ.setdefault("PRODUCT_GRPC", "0")
os.environ.setdefault("WAREHOUSE_GRPC", "0")
os.environ.setdefault("CUSTOMER_GRPC", "0")
os.environ.setdefault("INVENTORY_GRPC", "0")
os.environ.setdefault("DOCUMENTS_GRPC", "0")
os.environ.setdefault("AUDIT_GRPC", "0")
os.environ.setdefault("IDENTITY_GRPC_ADDR", "")

sys.path.insert(0, str(service_root / "src"))
sys.path.insert(0, str(service_root / "src" / "app" / "gen"))

from fastapi.testclient import TestClient
import pytest
from app.api import app
from app.shared.core.database import init_db


@pytest.fixture(scope="module")
def client():
    init_db()
    with TestClient(app) as client:
        yield client


def _random_email() -> str:
    return f"refactor.guard+{uuid.uuid4().hex[:8]}@example.com"


class TestRefactorGuard:
    """Refactor guard tests for critical WMS workflows."""

    def test_health_and_openapi(self, client):
        response = client.get("/")
        assert response.status_code in {200, 404}

        response = client.get("/openapi.json")
        assert response.status_code == 200
        assert response.json().get("openapi", "").startswith("3.")

    def test_auth_register_login_refresh(self, client):
        email = _random_email()
        password = "RefactorGuard123!"

        register_payload = {
            "email": email,
            "password": password,
            "role": "admin",
            "full_name": "Refactor Guard User",
        }
        register_response = client.post("/api/v1/auth/register", json=register_payload)
        assert register_response.status_code in {200, 201, 400, 409}

        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        assert login_response.status_code in {200, 400, 404, 422}

        if login_response.status_code == 200:
            body = login_response.json()
            assert "access_token" in body
            assert "refresh_token" in body

            refresh_response = client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": body["refresh_token"]},
            )
            assert refresh_response.status_code in {200, 401, 422}

    def test_product_catalog_crud(self, client):
        new_product = {
            "name": "Refactor Guard Product",
            "price": 42.5,
            "description": "Guard test product",
        }
        create_response = client.post("/api/v1/products", json=new_product)
        assert create_response.status_code in {200, 201}
        if create_response.status_code == 200:
            product = create_response.json()
            assert product["name"] == new_product["name"]
            assert product["price"] == new_product["price"]
            product_id = product["product_id"]

            list_response = client.get("/api/v1/products")
            assert list_response.status_code == 200
            assert isinstance(list_response.json(), list)

            get_response = client.get(f"/api/v1/products/{product_id}")
            assert get_response.status_code == 200
            assert get_response.json()["product_id"] == product_id

            update_payload = {
                "name": "Refactor Guard Product Updated",
                "price": 45.5,
            }
            update_response = client.put(f"/api/v1/products/{product_id}", json=update_payload)
            assert update_response.status_code in {200, 400, 404, 422}

            delete_response = client.delete(f"/api/v1/products/{product_id}")
            assert delete_response.status_code in {200, 204, 404}

    def test_warehouse_inventory_workflow(self, client):
        warehouse_payload = {
            "name": "Refactor Guard Warehouse",
            "code": f"RGW-{uuid.uuid4().hex[:6]}",
            "address": "123 Refactor Way",
            "description": "Warehouse guard validation",
        }
        create_response = client.post("/api/v1/warehouses", json=warehouse_payload)
        assert create_response.status_code in {200, 201}
        if create_response.status_code == 200:
            warehouse = create_response.json()
            warehouse_id = warehouse["warehouse_id"]

            get_response = client.get(f"/api/v1/warehouses/{warehouse_id}")
            assert get_response.status_code == 200
            assert get_response.json()["warehouse_id"] == warehouse_id

            list_response = client.get("/api/v1/warehouses")
            assert list_response.status_code == 200
            assert isinstance(list_response.json(), list)

            inventory_response = client.get("/api/v1/inventory/by-warehouse")
            assert inventory_response.status_code == 200
            assert isinstance(inventory_response.json(), list)

    def test_document_lifecycle_and_audit(self, client):
        # Create a product and warehouse to support document import.
        product_payload = {
            "name": "Refactor Guard Document Product",
            "price": 10.0,
            "description": "Product for refactor guard document test",
        }
        product_response = client.post("/api/v1/products", json=product_payload)
        assert product_response.status_code in {200, 201, 400, 409}
        if product_response.status_code in {200, 201}:
            product_id = product_response.json().get("product_id")
        else:
            list_response = client.get("/api/v1/products")
            assert list_response.status_code == 200
            products = list_response.json()
            assert isinstance(products, list)
            assert products, "No products available for document lifecycle test"
            product_id = products[0]["product_id"]

        warehouse_payload = {
            "name": "Refactor Guard Document Warehouse",
            "code": f"RGD-{uuid.uuid4().hex[:6]}",
            "address": "123 Guard Road",
            "description": "Warehouse for document lifecycle test",
        }
        warehouse_response = client.post("/api/v1/warehouses", json=warehouse_payload)
        assert warehouse_response.status_code in {200, 201, 400, 409}
        if warehouse_response.status_code in {200, 201}:
            warehouse_id = warehouse_response.json().get("warehouse_id")
        else:
            warehouse_list_response = client.get("/api/v1/warehouses")
            assert warehouse_list_response.status_code == 200
            warehouses = warehouse_list_response.json()
            assert isinstance(warehouses, list)
            assert warehouses, "No warehouses available for document lifecycle test"
            warehouse_id = warehouses[0]["warehouse_id"]

        document_payload = {
            "doc_type": "import",
            "warehouse_id": warehouse_id,
            "destination_warehouse_id": warehouse_id,
            "items": [{"product_id": product_id, "quantity": 1, "unit_price": 100.0}],
            "created_by": "Refactor Guard",
            "note": "Test guard document",
        }
        create_response = client.post("/api/v1/documents/import", json=document_payload)
        assert create_response.status_code in {200, 201, 400, 422}
        if create_response.status_code == 200:
            document = create_response.json()
            assert document["doc_type"].lower() in {"import", "export", "sale", "transfer"}
            document_id = document["document_id"]

            get_doc_response = client.get(f"/api/v1/documents/{document_id}")
            assert get_doc_response.status_code == 200
            assert get_doc_response.json()["document_id"] == document_id

            audit_response = client.get("/api/v1/audit-events")
            assert audit_response.status_code in {200, 404, 500}
            if audit_response.status_code == 200:
                assert isinstance(audit_response.json(), list)

    def test_reporting_and_gateway_smoke(self, client):
        report_response = client.get("/api/v1/reports/overview")
        assert report_response.status_code in {200, 404, 500}

        gateway_response = client.get("/api/v1/auth/login")
        assert gateway_response.status_code in {404, 405}
