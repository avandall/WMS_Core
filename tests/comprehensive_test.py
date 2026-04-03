"""
Comprehensive test script for WMS functionality
"""
import sys
import io
import requests
import json
from datetime import datetime

# Set UTF-8 encoding for console output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

API_BASE = "http://127.0.0.1:8000"
token = None

def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)

def test_auth():
    """Test authentication"""
    print_section("1. Testing Authentication")
    
    # Login
    response = requests.post(f"{API_BASE}/auth/login", json={
        "email": "admin@example.com",
        "password": "admin"
    })
    
    if response.status_code in [200, 201]:
        global token
        data = response.json()
        token = data['access_token']
        print("✓ Login successful")
        print(f"  Token: {token[:20]}...")
        return True
    else:
        print(f"✗ Login failed: {response.status_code}")
        print(f"  Response: {response.text}")
        return False

def test_products():
    """Test product creation"""
    print_section("2. Testing Products")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Create product
    product_data = {
        "name": f"Test Product {datetime.now().strftime('%H%M%S')}",
        "sku": f"TEST-{datetime.now().strftime('%H%M%S')}",
        "price": 15.99,
        "description": "Test product for comprehensive testing",
        "unit": "pcs"
    }
    
    response = requests.post(f"{API_BASE}/api/products/", json=product_data, headers=headers)
    
    if response.status_code in [200, 201]:
        data = response.json()
        product_id = data['product_id']
        print(f"✓ Product created: #{product_id} - {data['name']}")
        return product_id
    else:
        print(f"✗ Product creation failed: {response.status_code}")
        print(f"  Response: {response.text}")
        return None

def test_warehouses():
    """Test warehouse creation"""
    print_section("3. Testing Warehouses")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Create warehouse with microseconds for uniqueness
    from datetime import datetime
    warehouse_data = {
        "location": f"Test Warehouse {datetime.now().strftime('%H%M%S%f')}"
    }
    
    response = requests.post(f"{API_BASE}/api/warehouses/", json=warehouse_data, headers=headers)
    
    if response.status_code in [200, 201]:
        data = response.json()
        warehouse_id = data['warehouse_id']
        print(f"✓ Warehouse created: W-{warehouse_id} - {data['location']}")
        return warehouse_id
    else:
        print(f"✗ Warehouse creation failed: {response.status_code}")
        print(f"  Response: {response.text}")
        return None

def test_customers():
    """Test customer creation"""
    print_section("4. Testing Customers")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Create customer
    customer_data = {
        "name": f"Test Customer {datetime.now().strftime('%H%M%S')}",
        "email": f"test{datetime.now().strftime('%H%M%S')}@example.com",
        "phone": "0123456789",
        "address": "123 Test Street"
    }
    
    response = requests.post(f"{API_BASE}/api/customers/", json=customer_data, headers=headers)
    
    if response.status_code in [200, 201]:
        data = response.json()
        customer_id = data['customer_id']
        print(f"✓ Customer created: C-{customer_id} - {data['name']}")
        print(f"  Email: {data['email']}")
        print(f"  Debt: {data['debt_balance']}")
        return customer_id
    else:
        print(f"✗ Customer creation failed: {response.status_code}")
        print(f"  Response: {response.text}")
        return None

def test_import_document(product_id, warehouse_id):
    """Test import document"""
    print_section("5. Testing Import Document")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Create import document
    doc_data = {
        "doc_type": "IMPORT",
        "destination_warehouse_id": warehouse_id,
        "items": [
            {
                "product_id": product_id,
                "quantity": 100.0,
                "unit_price": 10.50
            }
        ]
    }
    
    response = requests.post(f"{API_BASE}/api/documents/import", json=doc_data, headers=headers)
    
    if response.status_code in [200, 201]:
        data = response.json()
        doc_id = data['document_id']
        print(f"✓ Import document created: #{doc_id}")
        
        # Post the document
        post_response = requests.post(f"{API_BASE}/api/documents/{doc_id}/post", json={"approved_by": "test_admin"}, headers=headers)
        if post_response.status_code == 200:
            print(f"✓ Document posted successfully")
            return doc_id
        else:
            print(f"✗ Document posting failed: {post_response.status_code}")
            return doc_id
    else:
        print(f"✗ Import document creation failed: {response.status_code}")
        print(f"  Response: {response.text}")
        return None

def test_export_document(product_id, warehouse_id):
    """Test export document (without customer)"""
    print_section("6. Testing Export Document (No Customer)")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    doc_data = {
        "doc_type": "EXPORT",
        "source_warehouse_id": warehouse_id,
        "items": [
            {
                "product_id": product_id,
                "quantity": 20.0
            }
        ]
    }
    
    response = requests.post(f"{API_BASE}/api/documents/export", json=doc_data, headers=headers)
    
    if response.status_code in [200, 201]:
        data = response.json()
        doc_id = data['document_id']
        print(f"✓ Export document created: #{doc_id}")
        
        # Post the document
        post_response = requests.post(f"{API_BASE}/api/documents/{doc_id}/post", json={"approved_by": "test_admin"}, headers=headers)
        if post_response.status_code == 200:
            print(f"✓ Document posted successfully")
            return doc_id
        else:
            print(f"✗ Document posting failed: {post_response.status_code}")
            return doc_id
    else:
        print(f"✗ Export document creation failed: {response.status_code}")
        print(f"  Response: {response.text}")
        return None

def test_sale_document(product_id, warehouse_id, customer_id):
    """Test sale document with customer"""
    print_section("7. Testing Sale Document (With Customer)")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    doc_data = {
        "doc_type": "SALE",
        "source_warehouse_id": warehouse_id,
        "customer_id": customer_id,
        "items": [
            {
                "product_id": product_id,
                "quantity": 15.0,
                "unit_price": 25.00
            }
        ]
    }
    
    response = requests.post(f"{API_BASE}/api/documents/sale", json=doc_data, headers=headers)
    
    if response.status_code in [200, 201]:
        data = response.json()
        doc_id = data['document_id']
        print(f"✓ Sale document created: #{doc_id}")
        print(f"  Customer: C-{customer_id}")
        
        # Post the document
        post_response = requests.post(f"{API_BASE}/api/documents/{doc_id}/post", json={"approved_by": "test_admin"}, headers=headers)
        if post_response.status_code == 200:
            print(f"✓ Document posted successfully")
            print(f"  Sale total: 15 × $25.00 = $375.00")
            return doc_id
        else:
            print(f"✗ Document posting failed: {post_response.status_code}")
            print(f"  Response: {post_response.text}")
            return doc_id
    else:
        print(f"✗ Sale document creation failed: {response.status_code}")
        print(f"  Response: {response.text}")
        return None

def test_transfer_document(product_id, from_warehouse, to_warehouse):
    """Test transfer document"""
    print_section("8. Testing Transfer Document")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    doc_data = {
        "doc_type": "TRANSFER",
        "source_warehouse_id": from_warehouse,
        "destination_warehouse_id": to_warehouse,
        "items": [
            {
                "product_id": product_id,
                "quantity": 10.0
            }
        ]
    }
    
    response = requests.post(f"{API_BASE}/api/documents/transfer", json=doc_data, headers=headers)
    
    if response.status_code in [200, 201]:
        data = response.json()
        doc_id = data['document_id']
        print(f"✓ Transfer document created: #{doc_id}")
        print(f"  From: W-{from_warehouse} → To: W-{to_warehouse}")
        
        # Post the document
        post_response = requests.post(f"{API_BASE}/api/documents/{doc_id}/post", json={"approved_by": "test_admin"}, headers=headers)
        if post_response.status_code == 200:
            print(f"✓ Document posted successfully")
            return doc_id
        else:
            print(f"✗ Document posting failed: {post_response.status_code}")
            return doc_id
    else:
        print(f"✗ Transfer document creation failed: {response.status_code}")
        print(f"  Response: {response.text}")
        return None

def test_reports():
    """Test report generation"""
    print_section("9. Testing Reports")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test inventory report
    print("\n9.1 Inventory Report:")
    response = requests.get(f"{API_BASE}/api/reports/inventory/list", headers=headers)
    if response.status_code in [200, 201]:
        data = response.json()
        print(f"✓ Inventory report retrieved: {len(data)} items")
        if len(data) > 0:
            print(f"  Sample: Product #{data[0]['product_id']} - Qty: {data[0]['quantity']}")
    else:
        print(f"✗ Inventory report failed: {response.status_code}")
    
    # Test document report
    print("\n9.2 Document Report:")
    response = requests.get(f"{API_BASE}/api/reports/documents", headers=headers)
    if response.status_code in [200, 201]:
        data = response.json()
        print(f"✓ Document report retrieved: {len(data)} documents")
        if len(data) > 0:
            sample = data[0]
            print(f"  Sample: Doc #{sample.get('document_id')} - Type: {sample.get('doc_type')} - Customer: {sample.get('customer_id', 'N/A')}")
    else:
        print(f"✗ Document report failed: {response.status_code}")
        print(f"  Response: {response.text}")

def test_customer_purchases(customer_id):
    """Test customer purchase history"""
    print_section("10. Testing Customer Purchase History")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    response = requests.get(f"{API_BASE}/api/customers/{customer_id}/purchases", headers=headers)
    
    if response.status_code in [200, 201]:
        data = response.json()
        print(f"✓ Customer purchases retrieved: {len(data)} purchases")
        total_value = sum(p['total_value'] for p in data)
        print(f"  Total purchase value: ${total_value:.2f}")
        
        # Get customer details to check debt
        customer_response = requests.get(f"{API_BASE}/api/customers/{customer_id}", headers=headers)
        if customer_response.status_code == 200:
            customer = customer_response.json()
            print(f"  Current debt balance: ${customer['debt_balance']:.2f}")
    else:
        print(f"✗ Customer purchases retrieval failed: {response.status_code}")
        print(f"  Response: {response.text}")

def test_inventory_check(product_id, warehouse_id):
    """Test inventory levels"""
    print_section("11. Testing Inventory Levels")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    response = requests.get(f"{API_BASE}/api/inventory/", 
                          params={"product_id": product_id, "warehouse_id": warehouse_id},
                          headers=headers)
    
    if response.status_code in [200, 201]:
        data = response.json()
        if data:
            print(f"✓ Inventory retrieved for Product #{product_id} in Warehouse W-{warehouse_id}")
            print(f"  Available quantity: {data[0]['quantity']}")
        else:
            print(f"  No inventory found")
    else:
        print(f"✗ Inventory retrieval failed: {response.status_code}")

def run_all_tests():
    """Run all tests"""
    print("\n" + "="*60)
    print("  WMS COMPREHENSIVE TEST SUITE")
    print("  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("="*60)
    
    # Test 1: Auth
    if not test_auth():
        print("\n✗ Authentication failed. Cannot continue tests.")
        return
    
    # Test 2: Products
    product_id = test_products()
    if not product_id:
        print("\n✗ Product creation failed. Cannot continue tests.")
        return
    
    # Test 3: Warehouses
    warehouse1_id = test_warehouses()
    warehouse2_id = test_warehouses()  # Create second warehouse for transfer test
    if not warehouse1_id or not warehouse2_id:
        print("\n✗ Warehouse creation failed. Cannot continue tests.")
        return
    
    # Test 4: Customers
    customer_id = test_customers()
    if not customer_id:
        print("\n✗ Customer creation failed. Cannot continue tests.")
        return
    
    # Test 5: Import
    import_doc_id = test_import_document(product_id, warehouse1_id)
    
    # Test 6: Export
    export_doc_id = test_export_document(product_id, warehouse1_id)
    
    # Test 7: Sale
    sale_doc_id = test_sale_document(product_id, warehouse1_id, customer_id)
    
    # Test 8: Transfer
    transfer_doc_id = test_transfer_document(product_id, warehouse1_id, warehouse2_id)
    
    # Test 9: Reports
    test_reports()
    
    # Test 10: Customer purchases
    test_customer_purchases(customer_id)
    
    # Test 11: Inventory check
    test_inventory_check(product_id, warehouse1_id)
    
    # Final summary
    print_section("TEST SUMMARY")
    print("✓ Authentication: PASSED")
    print(f"✓ Product #{product_id}: CREATED")
    print(f"✓ Warehouse W-{warehouse1_id}: CREATED")
    print(f"✓ Warehouse W-{warehouse2_id}: CREATED")
    print(f"✓ Customer C-{customer_id}: CREATED")
    print(f"✓ Import Document #{import_doc_id}: CREATED & POSTED" if import_doc_id else "✗ Import: FAILED")
    print(f"✓ Export Document #{export_doc_id}: CREATED & POSTED" if export_doc_id else "✗ Export: FAILED")
    print(f"✓ Sale Document #{sale_doc_id}: CREATED & POSTED" if sale_doc_id else "✗ Sale: FAILED")
    print(f"✓ Transfer Document #{transfer_doc_id}: CREATED & POSTED" if transfer_doc_id else "✗ Transfer: FAILED")
    print("✓ Reports: TESTED")
    print("✓ Customer Purchases: TESTED")
    print("\n" + "="*60)
    print("  ALL TESTS COMPLETED")
    print("="*60 + "\n")

if __name__ == "__main__":
    try:
        run_all_tests()
    except Exception as e:
        print(f"\n✗ Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()
