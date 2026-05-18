#!/usr/bin/env bash
set -euo pipefail

# Run Schemathesis contract tests against a running API.
# Usage: API_URL=http://localhost:8000 ./run_schemathesis.sh

if [ -z "${API_URL:-}" ]; then
  echo "Set API_URL environment variable to the base URL of the API (e.g. http://localhost:8000)"
  exit 0
fi

echo "Running Schemathesis against $API_URL/openapi.json"
schemathesis run "$API_URL/openapi.json" --checks all --max-examples 20
