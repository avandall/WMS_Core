from __future__ import annotations

import argparse
import datetime as dt
import http.client
import json
import subprocess
import sys
import time
import uuid


def _admin_token() -> str:
    code = """
import datetime as dt
import sqlite3
from app.shared.core.auth import create_token
from app.shared.core.settings import settings

con = sqlite3.connect('/tmp/wms-identity.db')
now = dt.datetime.now().isoformat(sep=' ')
con.execute(
    'insert or replace into users(user_id,email,hashed_password,role,full_name,is_active,created_at) '
    'values (?,?,?,?,?,?,?)',
    (1, 'trace-admin@example.com', 'not-used', 'admin', 'Trace Admin', 1, now),
)
con.commit()
print(create_token('1', settings.access_token_expire_minutes, {'role': 'admin'}))
""".strip()
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "identity-service", "python", "-c", code],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip().splitlines()[-1]


def _request(path: str, *, token: str, request_id: str) -> tuple[int, str, str]:
    conn = http.client.HTTPConnection("localhost", 8000, timeout=15)
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Request-ID": request_id,
    }
    conn.request("GET", path, headers=headers)
    response = conn.getresponse()
    body = response.read().decode("utf-8", errors="replace")
    traceparent = response.getheader("traceparent") or ""
    return response.status, body, traceparent


def _span_count(data: dict) -> int:
    return sum(len(trace.get("spans", [])) for trace in data.get("data", []))


def _jaeger_trace(trace_id: str, *, min_spans: int, retries: int = 10) -> dict:
    best = {"data": []}
    for attempt in range(retries):
        conn = http.client.HTTPConnection("localhost", 16686, timeout=15)
        conn.request("GET", f"/api/traces/{trace_id}")
        response = conn.getresponse()
        body = response.read().decode("utf-8", errors="replace")
        if response.status == 200:
            data = json.loads(body)
            if data.get("data"):
                best = data
                if _span_count(data) >= min_spans:
                    return data
        time.sleep(1 + attempt * 0.25)
    return best


def _trace_id(traceparent: str) -> str:
    parts = traceparent.split("-")
    if len(parts) < 4 or len(parts[1]) != 32:
        raise ValueError(f"Invalid traceparent header: {traceparent!r}")
    return parts[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Send a demo request and print its Jaeger trace.")
    parser.add_argument("--path", default="/api/v1/customers", help="Gateway path to call.")
    parser.add_argument(
        "--request-id",
        default=f"jaeger-demo-{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}",
        help="X-Request-ID to send.",
    )
    parser.add_argument("--min-spans", type=int, default=3, help="Wait until Jaeger has at least this many spans.")
    args = parser.parse_args()

    print("Creating demo admin token from identity-service...")
    token = _admin_token()

    print(f"Calling http://localhost:8000{args.path}")
    status, body, traceparent = _request(args.path, token=token, request_id=args.request_id)
    print(f"HTTP status: {status}")
    print(f"X-Request-ID: {args.request_id}")
    print(f"traceparent: {traceparent}")
    print(f"response body: {body[:500]}")

    trace_id = _trace_id(traceparent)
    print(f"\nWaiting for Jaeger trace: {trace_id}")
    data = _jaeger_trace(trace_id, min_spans=args.min_spans)
    traces = data.get("data", [])
    if not traces:
        print("No trace found in Jaeger yet. Try refreshing http://localhost:16686")
        return 1

    services = sorted(
        {
            process.get("serviceName")
            for trace in traces
            for process in trace.get("processes", {}).values()
            if process.get("serviceName")
        }
    )
    spans = [
        span.get("operationName")
        for trace in traces
        for span in trace.get("spans", [])
    ]

    print("\nJaeger trace found")
    print(f"Jaeger UI: http://localhost:16686/trace/{trace_id}")
    print(f"Span count: {_span_count(data)}")
    print(f"Services: {', '.join(services)}")
    print("Spans:")
    for span in spans:
        print(f"  - {span}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
