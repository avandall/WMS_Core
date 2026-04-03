"""
Integration tests for Warehouses API endpoints.
Tests warehouse creation, inventory management, and product movements.
"""

import httpx


TestClient = httpx.Client  # Type alias for test client


class TestWarehousesAPI:
    """Integration tests for Warehouses API."""

    def test_create_warehouse_success(self, client: TestClient):
        """Test creating a warehouse successfully."""
        warehouse_data = {"location": "Test Warehouse Location"}

        response = client.post("/api/warehouses/", json=warehouse_data)

        assert response.status_code == 200
        data = response.json()
        assert "warehouse_id" in data
        assert data["location"] == "Test Warehouse Location"
        assert data["inventory"] == []

        # Store warehouse ID for other tests
        self.warehouse_id = data["warehouse_id"]

    def test_get_warehouse_inventory(self, client: TestClient):
        """Test getting warehouse inventory."""
        # First create a warehouse
        warehouse_data = {"location": "Inventory Test Warehouse"}
        response = client.post("/api/warehouses/", json=warehouse_data)
        warehouse_id = response.json()["warehouse_id"]

        # Get warehouse inventory (should be empty)
        response = client.get(f"/api/warehouses/{warehouse_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["warehouse_id"] == warehouse_id
        assert data["inventory"] == []

    def test_get_nonexistent_warehouse(self, client: TestClient):
        """Test getting a nonexistent warehouse."""
        response = client.get("/api/warehouses/999")

        assert response.status_code == 404

    def test_add_product_to_warehouse(self, client: TestClient):
        """Test adding product to warehouse."""
        # Create warehouse
        warehouse_data = {"location": "Add Product Warehouse"}
        response = client.post("/api/warehouses/", json=warehouse_data)
        warehouse_id = response.json()["warehouse_id"]

        # Create product first
        product_data = {
            "product_id": 100,
            "name": "Warehouse Test Product",
            "price": 25.0,
        }
        client.post("/api/products/", json=product_data)

        # Add product to warehouse via import document
        import_doc = {
            "warehouse_id": warehouse_id,
            "items": [{"product_id": 100, "quantity": 50, "unit_price": 25.0}],
            "created_by": "tester",
            "note": "add via document",
        }
        response = client.post("/api/documents/import", json=import_doc)
        assert response.status_code == 200
        doc_id = response.json()["document_id"]
        # Post the document
        post_resp = client.post(
            f"/api/documents/{doc_id}/post", json={"approved_by": "manager"}
        )
        assert post_resp.status_code == 200

        # Verify product was added
        response = client.get(f"/api/warehouses/{warehouse_id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["inventory"]) == 1
        assert data["inventory"][0]["quantity"] == 50

    def test_add_product_to_nonexistent_warehouse(self, client: TestClient):
        """Test adding product to nonexistent warehouse."""
        import_doc = {
            "warehouse_id": 999,
            "items": [{"product_id": 100, "quantity": 10, "unit_price": 25.0}],
            "created_by": "tester",
        }
        response = client.post("/api/documents/import", json=import_doc)
        assert response.status_code == 404

    def test_add_invalid_quantity_to_warehouse(self, client: TestClient):
        """Test adding invalid quantity to warehouse."""
        # Create warehouse
        warehouse_data = {"location": "Invalid Quantity Warehouse"}
        response = client.post("/api/warehouses/", json=warehouse_data)
        warehouse_id = response.json()["warehouse_id"]

        # Try to add negative quantity
        import_doc = {
            "warehouse_id": warehouse_id,
            "items": [{"product_id": 100, "quantity": -5, "unit_price": 25.0}],
            "created_by": "tester",
        }
        response = client.post("/api/documents/import", json=import_doc)
        assert response.status_code == 422

    def test_add_more_product_to_existing_inventory(self, client: TestClient):
        """Test adding more quantity to existing product in warehouse."""
        # Create warehouse and product
        warehouse_data = {"location": "Existing Inventory Warehouse"}
        response = client.post("/api/warehouses/", json=warehouse_data)
        warehouse_id = response.json()["warehouse_id"]

        product_data = {
            "product_id": 200,
            "name": "Existing Inventory Product",
            "price": 30.0,
        }
        client.post("/api/products/", json=product_data)

        # Add initial quantity via import document
        import_doc_1 = {
            "warehouse_id": warehouse_id,
            "items": [{"product_id": 200, "quantity": 20, "unit_price": 30.0}],
            "created_by": "tester",
        }
        doc_resp = client.post("/api/documents/import", json=import_doc_1)
        doc_id = doc_resp.json()["document_id"]
        client.post(f"/api/documents/{doc_id}/post", json={"approved_by": "manager"})

        # Add more quantity via import document
        import_doc_2 = {
            "warehouse_id": warehouse_id,
            "items": [{"product_id": 200, "quantity": 15, "unit_price": 30.0}],
            "created_by": "tester",
        }
        doc_resp2 = client.post("/api/documents/import", json=import_doc_2)
        doc_id2 = doc_resp2.json()["document_id"]
        post2 = client.post(
            f"/api/documents/{doc_id2}/post", json={"approved_by": "manager"}
        )
        assert post2.status_code == 200

        # Verify total quantity
        response = client.get(f"/api/warehouses/{warehouse_id}")
        data = response.json()
        assert len(data["inventory"]) == 1
        assert data["inventory"][0]["quantity"] == 35

    def test_remove_product_from_warehouse(self, client: TestClient):
        """Test removing product from warehouse."""
        # Create warehouse, product, and add to inventory
        warehouse_data = {"location": "Remove Product Warehouse"}
        response = client.post("/api/warehouses/", json=warehouse_data)
        warehouse_id = response.json()["warehouse_id"]

        product_data = {"product_id": 300, "name": "Remove Test Product", "price": 40.0}
        client.post("/api/products/", json=product_data)

        # Add product to warehouse via import
        import_doc = {
            "warehouse_id": warehouse_id,
            "items": [{"product_id": 300, "quantity": 25, "unit_price": 40.0}],
            "created_by": "tester",
        }
        doc_resp = client.post("/api/documents/import", json=import_doc)
        doc_id = doc_resp.json()["document_id"]
        client.post(f"/api/documents/{doc_id}/post", json={"approved_by": "manager"})

        # Remove some quantity via export document
        export_doc = {
            "warehouse_id": warehouse_id,
            "items": [{"product_id": 300, "quantity": 10, "unit_price": 40.0}],
            "created_by": "tester",
        }
        doc_resp2 = client.post("/api/documents/export", json=export_doc)
        assert doc_resp2.status_code == 200
        doc_id2 = doc_resp2.json()["document_id"]
        post_resp = client.post(
            f"/api/documents/{doc_id2}/post", json={"approved_by": "manager"}
        )
        assert post_resp.status_code == 200

        # Verify remaining quantity
        response = client.get(f"/api/warehouses/{warehouse_id}")
        data = response.json()
        assert data["inventory"][0]["quantity"] == 15

    def test_remove_all_product_from_warehouse(self, client: TestClient):
        """Test removing all quantity of a product from warehouse."""
        # Create warehouse, product, and add to inventory
        warehouse_data = {"location": "Remove All Warehouse"}
        response = client.post("/api/warehouses/", json=warehouse_data)
        warehouse_id = response.json()["warehouse_id"]

        product_data = {"product_id": 400, "name": "Remove All Product", "price": 50.0}
        client.post("/api/products/", json=product_data)

        # Add product to warehouse via import
        import_doc = {
            "warehouse_id": warehouse_id,
            "items": [{"product_id": 400, "quantity": 10, "unit_price": 50.0}],
            "created_by": "tester",
        }
        doc_resp = client.post("/api/documents/import", json=import_doc)
        doc_id = doc_resp.json()["document_id"]
        client.post(f"/api/documents/{doc_id}/post", json={"approved_by": "manager"})

        # Remove all quantity via export
        export_doc = {
            "warehouse_id": warehouse_id,
            "items": [{"product_id": 400, "quantity": 10, "unit_price": 50.0}],
            "created_by": "tester",
        }
        doc_resp2 = client.post("/api/documents/export", json=export_doc)
        doc_id2 = doc_resp2.json()["document_id"]
        post2 = client.post(
            f"/api/documents/{doc_id2}/post", json={"approved_by": "manager"}
        )
        assert post2.status_code == 200

        # Verify product is completely removed
        response = client.get(f"/api/warehouses/{warehouse_id}")
        data = response.json()
        assert len(data["inventory"]) == 0

    def test_remove_insufficient_stock_from_warehouse(self, client: TestClient):
        """Test removing more quantity than available from warehouse."""
        # Create warehouse, product, and add to inventory
        warehouse_data = {"location": "Insufficient Stock Warehouse"}
        response = client.post("/api/warehouses/", json=warehouse_data)
        warehouse_id = response.json()["warehouse_id"]

        product_data = {
            "product_id": 500,
            "name": "Insufficient Stock Product",
            "price": 60.0,
        }
        client.post("/api/products/", json=product_data)

        # Add limited quantity via import
        import_doc = {
            "warehouse_id": warehouse_id,
            "items": [{"product_id": 500, "quantity": 5, "unit_price": 60.0}],
            "created_by": "tester",
        }
        doc_resp = client.post("/api/documents/import", json=import_doc)
        doc_id = doc_resp.json()["document_id"]
        client.post(f"/api/documents/{doc_id}/post", json={"approved_by": "manager"})

        # Try to remove more than available via export
        export_doc = {
            "warehouse_id": warehouse_id,
            "items": [{"product_id": 500, "quantity": 10, "unit_price": 60.0}],
            "created_by": "tester",
        }
        create_resp = client.post("/api/documents/export", json=export_doc)
        assert create_resp.status_code == 200
        doc_id2 = create_resp.json()["document_id"]
        post_resp = client.post(
            f"/api/documents/{doc_id2}/post", json={"approved_by": "manager"}
        )
        assert post_resp.status_code == 400

    def test_remove_product_not_in_warehouse(self, client: TestClient):
        """Test removing product that doesn't exist in warehouse."""
        # Create warehouse
        warehouse_data = {"location": "No Product Warehouse"}
        response = client.post("/api/warehouses/", json=warehouse_data)
        warehouse_id = response.json()["warehouse_id"]

        # Try to remove product not in warehouse via export
        export_doc = {
            "warehouse_id": warehouse_id,
            "items": [{"product_id": 600, "quantity": 5, "unit_price": 60.0}],
            "created_by": "tester",
        }
        create_resp = client.post("/api/documents/export", json=export_doc)
        # Product does not exist at all, so creation itself should fail.
        assert create_resp.status_code in (400, 404)

    def test_warehouse_inventory_workflow(self, client: TestClient):
        """Test complete warehouse inventory workflow."""
        # Create warehouse and product
        warehouse_data = {"location": "Workflow Warehouse"}
        response = client.post("/api/warehouses/", json=warehouse_data)
        warehouse_id = response.json()["warehouse_id"]

        product_data = {"product_id": 700, "name": "Workflow Product", "price": 75.0}
        client.post("/api/products/", json=product_data)

        # Initially empty
        response = client.get(f"/api/warehouses/{warehouse_id}")
        assert len(response.json()["inventory"]) == 0

        # Add products via import doc
        import_doc_1 = {
            "warehouse_id": warehouse_id,
            "items": [{"product_id": 700, "quantity": 100, "unit_price": 75.0}],
            "created_by": "tester",
        }
        resp1 = client.post("/api/documents/import", json=import_doc_1)
        doc_id1 = resp1.json()["document_id"]
        client.post(f"/api/documents/{doc_id1}/post", json={"approved_by": "manager"})

        response = client.get(f"/api/warehouses/{warehouse_id}")
        assert response.json()["inventory"][0]["quantity"] == 100

        # Add more via import doc
        import_doc_2 = {
            "warehouse_id": warehouse_id,
            "items": [{"product_id": 700, "quantity": 50, "unit_price": 75.0}],
            "created_by": "tester",
        }
        resp2 = client.post("/api/documents/import", json=import_doc_2)
        doc_id2 = resp2.json()["document_id"]
        client.post(f"/api/documents/{doc_id2}/post", json={"approved_by": "manager"})

        response = client.get(f"/api/warehouses/{warehouse_id}")
        assert response.json()["inventory"][0]["quantity"] == 150

        # Remove some via export doc
        export_doc = {
            "warehouse_id": warehouse_id,
            "items": [{"product_id": 700, "quantity": 75, "unit_price": 75.0}],
            "created_by": "tester",
        }
        resp3 = client.post("/api/documents/export", json=export_doc)
        doc_id3 = resp3.json()["document_id"]
        client.post(f"/api/documents/{doc_id3}/post", json={"approved_by": "manager"})

        response = client.get(f"/api/warehouses/{warehouse_id}")
        assert response.json()["inventory"][0]["quantity"] == 75
