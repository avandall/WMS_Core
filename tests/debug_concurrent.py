#!/usr/bin/env python
"""Debug ThreadPoolExecutor test"""
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

def test_req(i):
    try:
        r = requests.get('http://localhost:8000/api/products', timeout=15)
        print(f"Request {i}: Status {r.status_code}")
        return r.status_code == 200
    except Exception as e:
        print(f"Request {i}: Error - {type(e).__name__}: {str(e)[:50]}")
        return False

print("Testing ThreadPoolExecutor with 5 concurrent requests...")
with ThreadPoolExecutor(max_workers=5) as ex:
    futures = [ex.submit(test_req, i) for i in range(10)]
    success = sum(1 for f in as_completed(futures) if f.result())
    print(f"\nResults: {success}/10 succeeded")
