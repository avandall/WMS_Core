#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

# Auto-create and activate the local virtual environment if needed.
if [ -d ".venv" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
else
  echo "Creating local virtual environment in .venv"
  python3 -m venv .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate
  python3 -m pip install --upgrade pip setuptools wheel
  python3 -m pip install -r requirements.txt
fi

# Ensure imports resolve from the monolith source tree.
export PYTHONPATH="$PWD/src:$PWD"

# Ensure requirements are installed in an existing virtual environment too.
if ! python3 -c "import requests" >/dev/null 2>&1; then
  echo "Some dependencies are missing in .venv; installing requirements.txt..."
  python3 -m pip install -r requirements.txt
fi

echo "--- Refactor guard environment ---"
echo "Working dir: $PWD"
echo "Python: $(which python)"
echo "PYTHONPATH: $PYTHONPATH"
echo "-------------------------------"

# Install minimal missing runtime deps needed for the guard suite.
if ! python3 -c "import grpc" >/dev/null 2>&1; then
  echo "grpcio not installed. Installing grpcio==1.80.0..."
  python3 -m pip install grpcio==1.80.0
fi

if ! python3 -c "import pytest" >/dev/null 2>&1; then
  echo "pytest not installed. Installing pytest..."
  python3 -m pip install pytest
fi

# Ensure the refactor guard runs with local service mode and no gRPC proxies.
export TESTING=true
export DATABASE_URL="sqlite:///$PWD/tests/refactor_guard/refactor_guard.db"
export PRODUCT_GRPC=0
export WAREHOUSE_GRPC=0
export CUSTOMER_GRPC=0
export INVENTORY_GRPC=0
export DOCUMENTS_GRPC=0
export AUDIT_GRPC=0
export IDENTITY_GRPC_ADDR=

python3 -m pytest -q tests/refactor_guard
