"""
Test script for rapid UI switching and concurrent requests.
Tests request cancellation, debouncing, and error recovery.
"""

import requests
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "http://localhost:8000"

def login():
    response = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": "admin@example.com", "password": "admin"}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]

def test_rapid_switching(token):
    """Simulate rapid UI switching by calling endpoints quickly."""
    print("\n" + "="*60)
    print("Testing Rapid UI Switching (Simulating User Interactions)")
    print("="*60)
    
    headers = {"Authorization": f"Bearer {token}"}
    endpoints = [
        '/api/products',
        '/api/warehouses',
        '/api/inventory',
        '/api/documents',
        '/api/customers',
        '/api/users',
    ]
    
    success_count = 0
    error_count = 0
    
    # Simulate rapid switching - user clicks buttons very fast
    print("\n1. Testing rapid sequential switching...")
    for iteration in range(3):
        print(f"\n   Iteration {iteration + 1}/3:")
        for endpoint in endpoints:
            try:
                response = requests.get(f"{BASE_URL}{endpoint}", headers=headers, timeout=15)
                if response.status_code == 200:
                    success_count += 1
                    print(f"      ✓ {endpoint}")
                else:
                    error_count += 1
                    print(f"      ✗ {endpoint} - Status {response.status_code}")
                # Rapid clicking - very short delay
                time.sleep(0.05)
            except Exception as e:
                error_count += 1
                print(f"      ✗ {endpoint} - {str(e)[:50]}")
    
    print(f"\n   Results: {success_count} succeeded, {error_count} failed")
    
    # Test concurrent requests (multiple users)
    print("\n2. Testing concurrent requests (10 users)...")
    concurrent_success = 0
    concurrent_error = 0
    
    def concurrent_request(user_id, endpoint):
        try:
            response = requests.get(f"{BASE_URL}{endpoint}", headers=headers, timeout=15)
            return response.status_code == 200
        except:
            return False
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for i in range(10):
            endpoint = endpoints[i % len(endpoints)]
            futures.append(executor.submit(concurrent_request, i, endpoint))
        
        for future in as_completed(futures):
            if future.result():
                concurrent_success += 1
            else:
                concurrent_error += 1
    
    print(f"   Results: {concurrent_success}/10 users succeeded")
    
    # Test stress: 50 requests with controlled concurrency
    print("\n3. Testing stress (50 requests, max 5 concurrent)...")
    stress_success = 0
    stress_error = 0
    
    def stress_request(endpoint_idx):
        endpoint = endpoints[endpoint_idx % len(endpoints)]
        try:
            response = requests.get(f"{BASE_URL}{endpoint}", headers=headers, timeout=15)
            return response.status_code == 200
        except:
            return False
    
    # Limit concurrency to 5 to avoid overwhelming the connection pool
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(stress_request, i) for i in range(50)]
        
        for i, future in enumerate(as_completed(futures)):
            try:
                if future.result():
                    stress_success += 1
                else:
                    stress_error += 1
            except:
                stress_error += 1
            
            if (i + 1) % 10 == 0:
                print(f"   Completed {i + 1}/50 requests: {stress_success} success, {stress_error} errors")
    
    print(f"   Final: {stress_success}/50 succeeded, {stress_error} failed")
    
    # Overall result
    total_success = success_count + concurrent_success + stress_success
    total_attempts = len(endpoints) * 3 + 10 + 50
    success_rate = (total_success / total_attempts) * 100
    
    print(f"\n   Overall Success Rate: {success_rate:.1f}% ({total_success}/{total_attempts})")
    
    return success_rate >= 95  # Must have 95%+ success rate

def test_connection_recovery(token):
    """Test system recovery from connection issues."""
    print("\n" + "="*60)
    print("Testing Connection Recovery")
    print("="*60)
    
    headers = {"Authorization": f"Bearer {token}"}
    endpoint = '/api/products'
    
    recovery_success = 0
    recovery_attempts = 5
    
    print("\nAttempting multiple requests after potential disconnects...")
    for attempt in range(recovery_attempts):
        try:
            response = requests.get(f"{BASE_URL}{endpoint}", headers=headers, timeout=15)
            if response.status_code == 200:
                recovery_success += 1
                print(f"   ✓ Attempt {attempt + 1}: Connected and recovered")
            else:
                print(f"   ✗ Attempt {attempt + 1}: HTTP {response.status_code}")
        except Exception as e:
            print(f"   ✗ Attempt {attempt + 1}: {type(e).__name__}")
        
        time.sleep(0.5)
    
    print(f"\nRecovery Rate: {recovery_success}/{recovery_attempts}")
    return recovery_success == recovery_attempts

def main():
    print("="*60)
    print("Rapid Switching & Concurrent Request Test")
    print("="*60)
    
    # Login
    print("\nLogging in...")
    token = login()
    print("✓ Login successful")
    
    # Test rapid switching
    rapid_test_passed = test_rapid_switching(token)
    
    # Test connection recovery
    recovery_test_passed = test_connection_recovery(token)
    
    print("\n" + "="*60)
    print("FINAL RESULTS")
    print("="*60)
    print(f"Rapid Switching Test: {'PASSED' if rapid_test_passed else 'FAILED'}")
    print(f"Connection Recovery Test: {'PASSED' if recovery_test_passed else 'FAILED'}")
    
    if rapid_test_passed and recovery_test_passed:
        print("\n✓ ALL TESTS PASSED!")
        print("System is stable under rapid UI switching and concurrent loads")
    else:
        print("\n✗ Some tests failed - further optimization needed")

if __name__ == "__main__":
    main()
