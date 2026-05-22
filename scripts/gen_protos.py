from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROTO_ROOT = ROOT / "proto"


TARGETS = {
    "Services/identity-service": "src/identity_service/gen",
    "Services/customer-service": "src/customer_service/gen",
    "Services/product-service": "src/product_service/gen",
    "Services/warehouse-service": "src/warehouse_service/gen",
    "Services/inventory-service": "src/inventory_service/gen",
    "Services/documents-service": "src/documents_service/gen",
    "Services/audit-service": "src/audit_service/gen",
    "Services/reporting-service": "src/reporting_service/gen",
    "Services/ai-service": "src/ai_service/gen",
    "Services/api-gateway": "src/api_gateway/gen",
}


def main() -> None:
    proto_files = [str(p) for p in PROTO_ROOT.rglob("*.proto")]
    if not proto_files:
        raise SystemExit("No .proto files found")

    for service_dir, out_dir in TARGETS.items():
        out_path = ROOT / service_dir / out_dir
        out_path.mkdir(parents=True, exist_ok=True)

        cmd = [
            sys.executable,
            "-m",
            "grpc_tools.protoc",
            f"-I{PROTO_ROOT}",
            f"--python_out={out_path}",
            f"--grpc_python_out={out_path}",
            *proto_files,
        ]
        subprocess.check_call(cmd)


if __name__ == "__main__":
    main()
