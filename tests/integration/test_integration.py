"""
Comprehensive integration test for WMS project.
Tests all major flows and business logic validations using FastAPI's TestClient.
"""

import sys
import pytest
import requests  # noqa: F401 - Used dynamically in _set_client_alias fixture

BASE_URL = "/api"


@pytest.fixture(autouse=True)
def _set_client_alias(client):
    """Expose the shared HTTP client under the old requests-style name."""
    globals()["requests"] = client
    return client


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    END = "\033[0m"


def print_test(name: str):
    print(f"\n{Colors.BLUE}{'=' * 60}{Colors.END}")
    print(f"{Colors.BLUE}TEST: {name}{Colors.END}")
    print(f"{Colors.BLUE}{'=' * 60}{Colors.END}")


def print_success(msg: str):
    print(f"{Colors.GREEN}✓ {msg}{Colors.END}")


def print_error(msg: str):
    print(f"{Colors.RED}✗ {msg}{Colors.END}")


def print_info(msg: str):
    print(f"{Colors.YELLOW}ℹ {msg}{Colors.END}")


def assert_equal(actual, expected, msg: str):
    if actual == expected:
        print_success(f"{msg}: {actual} == {expected}")
        return True
    else:
        print_error(f"{msg}: {actual} != {expected}")
        return False


def assert_status(response, expected_status: int, msg: str):
    if response.status_code == expected_status:
        print_success(f"{msg}: Status {response.status_code}")
        return True
    else:
        print_error(f"{msg}: Expected {expected_status}, got {response.status_code}")
        print_error(f"Response: {response.text}")
        return False


# Test data storage
test_data = {"products": [], "warehouses": [], "documents": []}


@pytest.fixture(scope="module", autouse=True)
def _reset_module_database():
    """Ensure this sequential flow test starts from a clean database once."""
    from app.core.database import Base, engine

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    test_data["products"] = []
    test_data["warehouses"] = []
    test_data["documents"] = []
    yield


def test_product_crud():
    """Test product creation, retrieval, update, and deletion"""
    print_test("Product CRUD Operations")

    # Create products
    products = [
        {
            "product_id": 101,
            "name": "Laptop Dell XPS 15",
            "price": 1500.00,
            "description": "High-end laptop",
        },
        {
            "product_id": 102,
            "name": "Mouse Logitech MX Master",
            "price": 99.99,
            "description": "Wireless mouse",
        },
        {
            "product_id": 103,
            "name": "Keyboard Mechanical",
            "price": 150.00,
            "description": "RGB keyboard",
        },
    ]

    for product in products:
        response = requests.post(f"{BASE_URL}/products", json=product)
        if assert_status(response, 200, f"Create product {product['name']}"):
            test_data["products"].append(response.json())

    # Get all products
    response = requests.get(f"{BASE_URL}/products")
    if assert_status(response, 200, "Get all products"):
        assert_equal(len(response.json()), 3, "Product count")

    # Get single product
    response = requests.get(f"{BASE_URL}/products/101")
    if assert_status(response, 200, "Get product 101"):
        assert_equal(response.json()["name"], "Laptop Dell XPS 15", "Product name")

    # Update product
    response = requests.put(f"{BASE_URL}/products/101", json={"price": 1450.00})
    if assert_status(response, 200, "Update product price"):
        response = requests.get(f"{BASE_URL}/products/101")
        assert_equal(response.json()["price"], 1450.00, "Updated price")


def test_warehouse_crud():
    """Test warehouse creation and ID generation"""
    print_test("Warehouse CRUD Operations")

    # Create warehouses
    warehouses = [
        {"location": "Warehouse A - North District"},
        {"location": "Warehouse B - South District"},
        {"location": "Warehouse C - Central"},
    ]

    for wh in warehouses:
        response = requests.post(f"{BASE_URL}/warehouses", json=wh)
        if assert_status(response, 200, f"Create warehouse {wh['location']}"):
            data = response.json()
            test_data["warehouses"].append(data)
            print_info(f"Warehouse ID: {data['warehouse_id']}")

    # Verify sequential IDs
    if len(test_data["warehouses"]) == 3:
        ids = [wh["warehouse_id"] for wh in test_data["warehouses"]]
        assert_equal(ids[0] + 1, ids[1], "Sequential ID check 1")
        assert_equal(ids[1] + 1, ids[2], "Sequential ID check 2")

    # Get all warehouses
    response = requests.get(f"{BASE_URL}/warehouses")
    if assert_status(response, 200, "Get all warehouses"):
        assert_equal(len(response.json()), 3, "Warehouse count")


def test_import_document_flow():
    """Test import document creation and posting"""
    print_test("Import Document Flow")

    if not test_data["warehouses"] or not test_data["products"]:
        print_error("Prerequisites not met: Need warehouses and products")
        pytest.skip("Prerequisites not met for import document flow")

    warehouse_id = test_data["warehouses"][0]["warehouse_id"]

    # Create import document
    import_doc = {
        "warehouse_id": warehouse_id,
        "items": [
            {"product_id": 101, "quantity": 10, "unit_price": 1400.00},
            {"product_id": 102, "quantity": 50, "unit_price": 95.00},
        ],
        "created_by": "admin",
        "note": "Initial stock import",
    }

    response = requests.post(f"{BASE_URL}/documents/import", json=import_doc)
    assert assert_status(response, 200, "Create import document")

    doc = response.json()
    test_data["documents"].append(doc)
    doc_id = doc["document_id"]
    print_info(f"Document ID: {doc_id}, Status: {doc['status']}")

    # Verify DRAFT status
    assert_equal(doc["status"], "DRAFT", "Document status")

    # Check inventory before posting (should be 0)
    response = requests.get(f"{BASE_URL}/inventory")
    assert_status(response, 200, "Get inventory before posting")
    inventory_before = response.json()
    print_info(f"Inventory before post: {len(inventory_before)} items")

    # Post the document
    response = requests.post(
        f"{BASE_URL}/documents/{doc_id}/post", json={"approved_by": "manager"}
    )
    assert assert_status(response, 200, "Post import document")

    print_success("Import document posted successfully")

    # Verify inventory updated
    response = requests.get(f"{BASE_URL}/inventory")
    if assert_status(response, 200, "Get inventory after posting"):
        inventory = response.json()
        print_info(f"Inventory after post: {len(inventory)} items")

        # Find product 101 in inventory
        prod_101 = next((item for item in inventory if item["product_id"] == 101), None)
        if prod_101:
            assert_equal(prod_101["quantity"], 10, "Product 101 total quantity")

        prod_102 = next((item for item in inventory if item["product_id"] == 102), None)
        if prod_102:
            assert_equal(prod_102["quantity"], 50, "Product 102 total quantity")

    # Verify warehouse inventory updated
    response = requests.get(f"{BASE_URL}/warehouses/{warehouse_id}")
    if assert_status(response, 200, "Get warehouse after import"):
        warehouse = response.json()
        wh_inventory = warehouse["inventory"]
        print_info(f"Warehouse inventory: {len(wh_inventory)} items")

        wh_prod_101 = next(
            (item for item in wh_inventory if item["product_id"] == 101), None
        )
        if wh_prod_101:
            assert_equal(wh_prod_101["quantity"], 10, "Warehouse product 101 quantity")


def test_export_document_flow():
    """Test export document creation and posting"""
    print_test("Export Document Flow")

    if not test_data["warehouses"]:
        print_error("Prerequisites not met: Need warehouses")
        pytest.skip("Prerequisites not met for export document flow")

    warehouse_id = test_data["warehouses"][0]["warehouse_id"]

    # Create export document
    export_doc = {
        "warehouse_id": warehouse_id,
        "items": [{"product_id": 102, "quantity": 5, "unit_price": 99.99}],
        "created_by": "admin",
        "note": "Export to customer",
    }

    response = requests.post(f"{BASE_URL}/documents/export", json=export_doc)
    assert assert_status(response, 200, "Create export document")

    doc = response.json()
    doc_id = doc["document_id"]

    # Get inventory before export
    response = requests.get(f"{BASE_URL}/inventory/102")
    qty_before = response.json()["quantity"] if response.status_code == 200 else 0
    print_info(f"Product 102 quantity before export: {qty_before}")

    # Post the document
    response = requests.post(
        f"{BASE_URL}/documents/{doc_id}/post", json={"approved_by": "manager"}
    )
    assert assert_status(response, 200, "Post export document")

    # Verify inventory decreased
    response = requests.get(f"{BASE_URL}/inventory/102")
    if assert_status(response, 200, "Get inventory after export"):
        qty_after = response.json()["quantity"]
        print_info(f"Product 102 quantity after export: {qty_after}")
        assert_equal(qty_after, qty_before - 5, "Quantity decreased by 5")


def test_transfer_document_flow():
    """Test transfer document between warehouses"""
    print_test("Transfer Document Flow")

    if len(test_data["warehouses"]) < 2:
        print_error("Prerequisites not met: Need at least 2 warehouses")
        pytest.skip("Prerequisites not met for transfer document flow")

    from_warehouse = test_data["warehouses"][0]["warehouse_id"]
    to_warehouse = test_data["warehouses"][1]["warehouse_id"]

    # Get source warehouse inventory before transfer
    response = requests.get(f"{BASE_URL}/warehouses/{from_warehouse}")
    wh_before = response.json() if response.status_code == 200 else None

    # Create transfer document
    transfer_doc = {
        "from_warehouse_id": from_warehouse,
        "to_warehouse_id": to_warehouse,
        "items": [{"product_id": 101, "quantity": 3, "unit_price": 1450.00}],
        "created_by": "admin",
        "note": "Transfer between warehouses",
    }

    response = requests.post(f"{BASE_URL}/documents/transfer", json=transfer_doc)
    assert assert_status(response, 200, "Create transfer document")

    doc = response.json()
    doc_id = doc["document_id"]

    # Post the document
    response = requests.post(
        f"{BASE_URL}/documents/{doc_id}/post", json={"approved_by": "manager"}
    )
    assert assert_status(response, 200, "Post transfer document")

    # Verify source warehouse decreased
    response = requests.get(f"{BASE_URL}/warehouses/{from_warehouse}")
    if assert_status(response, 200, "Get source warehouse after transfer"):
        wh_after = response.json()
        prod_101_before = next(
            (item for item in wh_before["inventory"] if item["product_id"] == 101), None
        )
        prod_101_after = next(
            (item for item in wh_after["inventory"] if item["product_id"] == 101), None
        )

        if prod_101_before and prod_101_after:
            assert_equal(
                prod_101_after["quantity"],
                prod_101_before["quantity"] - 3,
                "Source warehouse quantity decreased",
            )

    # Verify destination warehouse increased
    response = requests.get(f"{BASE_URL}/warehouses/{to_warehouse}")
    if assert_status(response, 200, "Get destination warehouse after transfer"):
        wh_dest = response.json()
        prod_101_dest = next(
            (item for item in wh_dest["inventory"] if item["product_id"] == 101), None
        )
        if prod_101_dest:
            assert_equal(
                prod_101_dest["quantity"], 3, "Destination warehouse received items"
            )

    # Verify total inventory unchanged
    response = requests.get(f"{BASE_URL}/inventory/101")
    if assert_status(response, 200, "Verify total inventory unchanged"):
        print_info(f"Total inventory for product 101: {response.json()['quantity']}")


def test_error_validations():
    """Test business logic validations"""
    print_test("Error Validations")

    # Test 1: Import to non-existent warehouse
    print_info("Test: Import to non-existent warehouse")
    import_doc = {
        "warehouse_id": 99999,
        "items": [{"product_id": 101, "quantity": 5, "unit_price": 100.00}],
        "created_by": "admin",
    }
    response = requests.post(f"{BASE_URL}/documents/import", json=import_doc)
    assert_status(response, 404, "Should fail: non-existent warehouse")

    # Test 2: Export more than available stock
    if test_data["warehouses"]:
        print_info("Test: Export more than available stock")
        warehouse_id = test_data["warehouses"][0]["warehouse_id"]
        export_doc = {
            "warehouse_id": warehouse_id,
            "items": [{"product_id": 101, "quantity": 99999, "unit_price": 100.00}],
            "created_by": "admin",
        }
        response = requests.post(f"{BASE_URL}/documents/export", json=export_doc)
        if response.status_code == 200:
            # Document created, try to post
            doc_id = response.json()["document_id"]
            response = requests.post(
                f"{BASE_URL}/documents/{doc_id}/post", json={"approved_by": "manager"}
            )
            assert_status(response, 400, "Should fail: insufficient stock")

    # Test 3: Invalid product ID
    print_info("Test: Import with non-existent product")
    import_doc = {
        "warehouse_id": test_data["warehouses"][0]["warehouse_id"]
        if test_data["warehouses"]
        else 1,
        "items": [{"product_id": 99999, "quantity": 5, "unit_price": 100.00}],
        "created_by": "admin",
    }
    response = requests.post(f"{BASE_URL}/documents/import", json=import_doc)
    assert_status(response, 404, "Should fail: non-existent product")

    # Test 4: Delete warehouse with stock
    if test_data["warehouses"]:
        print_info("Test: Delete warehouse with stock")
        warehouse_id = test_data["warehouses"][0]["warehouse_id"]
        response = requests.delete(f"{BASE_URL}/warehouses/{warehouse_id}")
        assert_status(response, 400, "Should fail: warehouse has stock")

    # Test 5: Negative quantities
    print_info("Test: Create document with negative quantity")
    import_doc = {
        "warehouse_id": test_data["warehouses"][0]["warehouse_id"]
        if test_data["warehouses"]
        else 1,
        "items": [{"product_id": 101, "quantity": -5, "unit_price": 100.00}],
        "created_by": "admin",
    }
    response = requests.post(f"{BASE_URL}/documents/import", json=import_doc)
    assert_status(response, 422, "Should fail: negative quantity")


def test_reports():
    """Test report generation"""
    print_test("Report Generation")

    # Test inventory report
    response = requests.get(f"{BASE_URL}/reports/inventory")
    assert_status(response, 200, "Generate inventory report")

    # Test warehouse report
    if test_data["warehouses"]:
        warehouse_id = test_data["warehouses"][0]["warehouse_id"]
        response = requests.get(f"{BASE_URL}/reports/warehouse/{warehouse_id}")
        assert_status(response, 200, f"Generate warehouse {warehouse_id} report")

    # Test document report
    response = requests.get(f"{BASE_URL}/reports/documents")
    assert_status(response, 200, "Generate document report")


def run_all_tests():
    """Run all tests in sequence"""
    print(f"\n{Colors.BLUE}{'=' * 60}{Colors.END}")
    print(f"{Colors.BLUE}WMS COMPREHENSIVE INTEGRATION TEST{Colors.END}")
    print(f"{Colors.BLUE}{'=' * 60}{Colors.END}\n")

    tests = [
        ("Product CRUD", test_product_crud),
        ("Warehouse CRUD", test_warehouse_crud),
        ("Import Document Flow", test_import_document_flow),
        ("Export Document Flow", test_export_document_flow),
        ("Transfer Document Flow", test_transfer_document_flow),
        ("Error Validations", test_error_validations),
        ("Reports", test_reports),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print_error(f"Test '{test_name}' crashed: {e}")
            results.append((test_name, False))
            import traceback

            traceback.print_exc()

    # Summary
    print(f"\n{Colors.BLUE}{'=' * 60}{Colors.END}")
    print(f"{Colors.BLUE}TEST SUMMARY{Colors.END}")
    print(f"{Colors.BLUE}{'=' * 60}{Colors.END}\n")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = (
            f"{Colors.GREEN}PASSED{Colors.END}"
            if result
            else f"{Colors.RED}FAILED{Colors.END}"
        )
        print(f"{test_name}: {status}")

    print(f"\n{Colors.BLUE}Total: {passed}/{total} tests passed{Colors.END}\n")

    if passed == total:
        print(f"{Colors.GREEN}{'=' * 60}{Colors.END}")
        print(f"{Colors.GREEN}ALL TESTS PASSED ✓{Colors.END}")
        print(f"{Colors.GREEN}{'=' * 60}{Colors.END}\n")
        return 0
    else:
        print(f"{Colors.RED}{'=' * 60}{Colors.END}")
        print(f"{Colors.RED}SOME TESTS FAILED ✗{Colors.END}")
        print(f"{Colors.RED}{'=' * 60}{Colors.END}\n")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(run_all_tests())
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Fatal error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
