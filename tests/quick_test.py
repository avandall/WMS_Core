"""Quick test for users, customers, and inventory report endpoints"""
import requests
import sys

API_BASE = "http://127.0.0.1:8000"

# Login first
print("1. Testing Login...")
response = requests.post(f"{API_BASE}/auth/login", json={
    "email": "admin@example.com",
    "password": "admin"
})

if response.status_code == 200:
    token = response.json()['access_token']
    print("   ✓ Login successful")
    headers = {"Authorization": f"Bearer {token}"}
else:
    print(f"   ✗ Login failed: {response.status_code}")
    print(f"   Response: {response.text}")
    sys.exit(1)

# Test Users endpoint
print("\n2. Testing Users List...")
response = requests.get(f"{API_BASE}/api/users", headers=headers)
if response.status_code == 200:
    users = response.json()
    print(f"   ✓ Users list retrieved: {len(users)} users")
else:
    print(f"   ✗ Users list failed: {response.status_code}")
    print(f"   Response: {response.text}")

# Test Customers endpoint
print("\n3. Testing Customers List...")
response = requests.get(f"{API_BASE}/api/customers", headers=headers)
if response.status_code == 200:
    customers = response.json()
    print(f"   ✓ Customers list retrieved: {len(customers)} customers")
else:
    print(f"   ✗ Customers list failed: {response.status_code}")
    print(f"   Response: {response.text}")

# Test Inventory Report
print("\n4. Testing Inventory Report...")
response = requests.get(f"{API_BASE}/api/reports/inventory/list", headers=headers)
if response.status_code == 200:
    inventory = response.json()
    print(f"   ✓ Inventory report retrieved: {len(inventory)} items")
    if len(inventory) > 0:
        print(f"   Sample: Product #{inventory[0]['product_id']} in Warehouse W-{inventory[0]['warehouse_id']}: {inventory[0]['quantity']} units")
else:
    print(f"   ✗ Inventory report failed: {response.status_code}")
    print(f"   Response: {response.text}")

# Test Document Report with customer_id
print("\n5. Testing Document Report...")
response = requests.get(f"{API_BASE}/api/reports/documents", headers=headers)
if response.status_code == 200:
    documents = response.json()
    print(f"   ✓ Document report retrieved: {len(documents)} documents")
    if len(documents) > 0:
        sample = documents[0]
        customer_info = f"Customer: {sample.get('customer_id', 'N/A')}" if sample.get('customer_id') else "No customer"
        print(f"   Sample: Doc #{sample['document_id']} - Type: {sample['doc_type']} - {customer_info}")
else:
    print(f"   ✗ Document report failed: {response.status_code}")
    print(f"   Response: {response.text}")

print("\n" + "="*60)
print("All endpoint tests completed!")
print("="*60)
