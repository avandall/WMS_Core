"""
Test script for session management and sales report functionality.
Tests:
1. Multiple rapid API calls to verify session stability
2. Sales report endpoint with various filters
"""

import requests
import time

BASE_URL = "http://localhost:8000"

def login():
    response = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": "admin@example.com", "password": "admin"}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]

def test_session_stability(token):
    """Test that customers and users endpoints remain stable after multiple calls."""
    print("\n" + "="*60)
    print("Testing Session Stability (20 rapid calls each)")
    print("="*60)
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test customers endpoint with rapid consecutive calls
    print("\n1. Testing Customers endpoint...")
    for i in range(20):
        response = requests.get(f"{BASE_URL}/api/customers", headers=headers)
        if response.status_code != 200:
            print(f"   ✗ Call {i+1} failed: {response.status_code} - {response.text}")
            return False
        if i % 5 == 4:
            print(f"   ✓ Completed {i+1}/20 calls")
    print("   ✓ All 20 customers calls successful")
    
    # Small delay
    time.sleep(0.5)
    
    # Test users endpoint with rapid consecutive calls
    print("\n2. Testing Users endpoint...")
    for i in range(20):
        response = requests.get(f"{BASE_URL}/api/users", headers=headers)
        if response.status_code != 200:
            print(f"   ✗ Call {i+1} failed: {response.status_code} - {response.text}")
            return False
        if i % 5 == 4:
            print(f"   ✓ Completed {i+1}/20 calls")
    print("   ✓ All 20 users calls successful")
    
    # Test alternating calls
    print("\n3. Testing alternating calls (customers/users)...")
    for i in range(20):
        endpoint = "/api/customers" if i % 2 == 0 else "/api/users"
        response = requests.get(f"{BASE_URL}{endpoint}", headers=headers)
        if response.status_code != 200:
            print(f"   ✗ Call {i+1} to {endpoint} failed: {response.status_code}")
            return False
        if i % 5 == 4:
            print(f"   ✓ Completed {i+1}/20 alternating calls")
    print("   ✓ All 20 alternating calls successful")
    
    return True

def test_sales_report(token):
    """Test the new sales analytics report endpoint."""
    print("\n" + "="*60)
    print("Testing Sales Report Endpoint")
    print("="*60)
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test 1: Get all sales
    print("\n1. Testing sales report (all data)...")
    response = requests.get(f"{BASE_URL}/api/reports/sales", headers=headers)
    if response.status_code != 200:
        print(f"   ✗ Failed: {response.status_code} - {response.text}")
        return False
    
    data = response.json()
    print(f"   ✓ Success!")
    print(f"   Summary:")
    print(f"      - Total Sales: ${data['summary']['total_sales']:,.2f}")
    print(f"      - Total Debt: ${data['summary']['total_debt']:,.2f}")
    print(f"      - Transactions: {data['summary']['transaction_count']}")
    print(f"      - Unique Customers: {data['summary']['unique_customers']}")
    
    if data['sales']:
        print(f"\n   Sample Sale:")
        sale = data['sales'][0]
        print(f"      - Document ID: {sale['document_id']}")
        print(f"      - Salesperson: {sale['salesperson']}")
        print(f"      - Customer: {sale['customer_name']}")
        print(f"      - Sale Amount: ${sale['total_sale']:,.2f}")
        print(f"      - Customer Debt: ${sale['customer_debt']:,.2f}")
    
    # Test 2: Filter by customer
    print("\n2. Testing sales report with customer filter...")
    response = requests.get(f"{BASE_URL}/api/reports/sales?customer_id=1", headers=headers)
    if response.status_code != 200:
        print(f"   ✗ Failed: {response.status_code}")
        return False
    data = response.json()
    print(f"   ✓ Filtered to customer #1: {data['summary']['transaction_count']} transactions")
    
    # Test 3: Filter by salesperson
    print("\n3. Testing sales report with salesperson filter...")
    response = requests.get(f"{BASE_URL}/api/reports/sales?salesperson=admin", headers=headers)
    if response.status_code != 200:
        print(f"   ✗ Failed: {response.status_code}")
        return False
    data = response.json()
    print(f"   ✓ Filtered to salesperson 'admin': {data['summary']['transaction_count']} transactions")
    
    # Test 4: Date range filter
    print("\n4. Testing sales report with date range...")
    response = requests.get(
        f"{BASE_URL}/api/reports/sales?start_date=2026-01-01&end_date=2026-12-31",
        headers=headers
    )
    if response.status_code != 200:
        print(f"   ✗ Failed: {response.status_code}")
        return False
    data = response.json()
    print(f"   ✓ Filtered to 2026: {data['summary']['transaction_count']} transactions")
    
    return True

def main():
    print("="*60)
    print("WMS Session Stability & Sales Report Test")
    print("="*60)
    
    # Login
    print("\nLogging in...")
    token = login()
    print("✓ Login successful")
    
    # Test session stability
    if not test_session_stability(token):
        print("\n✗ Session stability test FAILED")
        return
    
    print("\n✓ Session stability test PASSED")
    
    # Test sales report
    if not test_sales_report(token):
        print("\n✗ Sales report test FAILED")
        return
    
    print("\n✓ Sales report test PASSED")
    
    print("\n" + "="*60)
    print("ALL TESTS PASSED!")
    print("="*60)
    print("\nSummary:")
    print("  • Session management is stable (60+ rapid API calls)")
    print("  • Sales report endpoint working with all filters")
    print("  • No DetachedInstanceError or session issues")

if __name__ == "__main__":
    main()
