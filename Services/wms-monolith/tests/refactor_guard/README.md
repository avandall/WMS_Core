# Refactor Guard Test Batch

This directory contains a dedicated regression guard suite for the microservices refactor.

## Purpose
These tests exercise the core WMS workflows and public API boundaries that should remain stable during refactor phases:

- authentication and user lifecycle
- product catalog CRUD
- warehouse and inventory workflows
- document lifecycle and audit behavior
- public API health and OpenAPI contract

## How to run

```bash
cd Services/wms-monolith
chmod +x tests/refactor_guard/run_refactor_guard.sh
./tests/refactor_guard/run_refactor_guard.sh
```

This script now auto-creates and activates `.venv` if needed, sets `PYTHONPATH` for the monolith source tree, and installs `requirements.txt` into that environment when necessary.

Or directly:

```bash
cd Services/wms-monolith
export TESTING=true
export PRODUCT_GRPC=0
export WAREHOUSE_GRPC=0
export CUSTOMER_GRPC=0
export INVENTORY_GRPC=0
export DOCUMENTS_GRPC=0
export AUDIT_GRPC=0
export IDENTITY_GRPC_ADDR=
pytest -q tests/refactor_guard
```

Note: `tests/refactor_guard/test_refactor_guard.py` uses `os.environ.setdefault(...)` to keep the defaults above,
but allows CI/scripts to override env vars if needed.

## CI integration

The refactor guard suite is now executed in GitHub Actions as part of the `CI` workflow in `.github/workflows/ci.yml`.
It runs after the unit test stage using `Services/wms-monolith/tests/refactor_guard/run_refactor_guard.sh`.

## Goal
Keep this guard suite small, fast, and stable. Use it before and after each refactor phase to confirm core behavior remains intact.
