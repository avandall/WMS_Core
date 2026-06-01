#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT_DIR"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-wms-gateway-e2e}"
BUILD_FLAG="${BUILD_FLAG---build}"

cleanup() {
  docker compose -p "$COMPOSE_PROJECT_NAME" -f "$COMPOSE_FILE" down -v
}
trap cleanup EXIT

docker compose -p "$COMPOSE_PROJECT_NAME" -f "$COMPOSE_FILE" up -d $BUILD_FLAG identity-service customer-service
docker compose -p "$COMPOSE_PROJECT_NAME" -f "$COMPOSE_FILE" up -d $BUILD_FLAG --no-deps api-gateway

echo "Waiting for API Gateway health..."
for i in $(seq 1 60); do
  if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
    break
  fi
  if [ "$i" = "60" ]; then
    docker compose -p "$COMPOSE_PROJECT_NAME" -f "$COMPOSE_FILE" ps
    docker compose -p "$COMPOSE_PROJECT_NAME" -f "$COMPOSE_FILE" logs --tail=120 api-gateway identity-service customer-service
    exit 1
  fi
  sleep 2
done

TOKEN="$(docker compose -p "$COMPOSE_PROJECT_NAME" -f "$COMPOSE_FILE" exec -T identity-service python /app/scripts/bootstrap_e2e_identity.py | tail -n 1)"
if [ -z "$TOKEN" ]; then
  echo "Failed to bootstrap E2E access token"
  exit 1
fi

export GATEWAY_URL="${GATEWAY_URL:-http://localhost:8000}"
export E2E_ACCESS_TOKEN="$TOKEN"

if command -v uv >/dev/null 2>&1; then
  uv run --group dev pytest -q tests/contract tests/e2e
elif python3 -c "import httpx, pytest" >/dev/null 2>&1; then
  python3 -m pytest -q tests/contract tests/e2e
else
  echo "pytest/httpx are required. Install them or run via uv."
  exit 1
fi
