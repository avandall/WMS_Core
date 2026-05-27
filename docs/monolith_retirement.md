# Monolith Retirement

Phase 16 removes the monolith from the active development path. Phase O freezes the remaining
tree as a read-only archive with an explicit rollback reference.

## Status

`Services/wms-monolith/` is archived reference code and is now frozen read-only reference code.
It is intentionally not part of:

- root `uv` workspace members
- default CI jobs
- root Docker Compose services
- gRPC proto generation targets
- gateway contract/E2E test flow

The active public entrypoint is `Services/api-gateway/`, backed by service-owned gRPC
packages and local datastores.

## Retirement Decision

Decision: keep `Services/wms-monolith/` as read-only reference until the next accepted tagged
service release, then delete it in a dedicated commit if no rollback/parity investigation is open.
The rollback reference tag is `phase-o-monolith-archive-exit`.

Phase O confirms:

1. API Gateway OpenAPI parity is accepted for the required business workflows.
2. Service-owned seed/dev fixtures replace monolith seed scripts.
3. Production deployment automation exists for service migrations and rollback.
4. No active script, CI job, Compose service, or deployment manifest imports or executes
   monolith internals.

Changes to `Services/wms-monolith/` must be rare and explicitly labeled as archive/reference
maintenance. Do not add new runtime features, migrations, fixtures, generated protos, CI jobs, or
deployment scripts under this tree.

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

Do not start work from monolith commands such as `Services/wms-monolith/start.sh`,
`Services/wms-monolith/run_tests.sh`, or `Services/wms-monolith/scripts/seed.py`; those are
historical archive commands only.
