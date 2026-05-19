from __future__ import annotations

import importlib
import sys


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: run_grpc_service.py <service_package>", file=sys.stderr)
        return 2

    module = importlib.import_module(f"{sys.argv[1]}.main")
    module.main_grpc()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
