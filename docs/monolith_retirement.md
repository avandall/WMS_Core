# Monolith Retirement

Phase 16 removes the monolith from the active development path while keeping it as an
archive for parity checks and historical reference.

## Status

`Services/wms-monolith/` is archived reference code. It is intentionally not part of:

- root `uv` workspace members
- default CI jobs
- root Docker Compose services
- gRPC proto generation targets
- gateway contract/E2E test flow

The active public entrypoint is `Services/api-gateway/`, backed by service-owned gRPC
packages and local datastores.

## Retirement Decision

The final delete/archive decision should happen after:

1. API Gateway OpenAPI parity is accepted for the required business workflows.
2. Service-owned seed/dev fixtures replace monolith seed scripts.
3. Production deployment automation exists for service migrations and rollback.
4. The team confirms no dashboard or operational script imports monolith internals.

Until then, changes to `Services/wms-monolith/` should be rare and explicitly labeled as
archive/reference maintenance.

## Fixture Ownership

Remaining seed data should move to service-owned fixtures. Phase L adds service-owned fixture
entrypoints so active dev/test flows no longer need monolith seed scripts:

| Fixture area | Target owner | Fixture command |
| --- | --- | --- |
| users/auth | identity-service | `identity-fixtures` |
| customers/purchases | customer-service | `customer-fixtures` |
| products/catalog | product-service | `product-fixtures` |
| warehouses/positions | warehouse-service | `warehouse-fixtures` |
| inventory stock | inventory-service | `inventory-fixtures` |
| documents/document_items | documents-service | `documents-fixtures` |
| audit examples | audit-service | `audit-fixtures` |
| reporting read models | reporting-service | `reporting-fixtures` |
| AI/vector examples | ai-service | future opt-in `ai-fixtures` when AI fixture data is needed |

## Contributor Entry Points

Use these commands for active development:

```bash
uv run --group dev pytest -q tests/contract/test_release_ops_contract.py
tests/e2e/run_gateway_stack_tests.sh
docker compose up -d
```

AI remains explicit:

```bash
docker compose --profile ai up -d ai-service
```
