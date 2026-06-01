# Data Ownership Baseline

Phase 10 starts the move from a monolith-shaped shared schema to service-owned datastores.

## Local Compose Strategy

Root `docker-compose.yml` now gives every service its own datastore connection instead of inheriting one shared `DATABASE_URL`.

| Service | Local datastore | Tables initialized today |
| --- | --- | --- |
| `identity-service` | `sqlite:////tmp/wms-identity.db` | `users` |
| `customer-service` | `sqlite:////tmp/wms-customer.db` | `customers` |
| `product-service` | `sqlite:////tmp/wms-product.db` | `products` |
| `warehouse-service` | `sqlite:////tmp/wms-warehouse.db` | `warehouses`, `positions` |
| `inventory-service` | `sqlite:////tmp/wms-inventory.db` | `inventory`, `warehouse_inventory`, `inventory_movement_ledger` |
| `documents-service` | `sqlite:////tmp/wms-documents.db` | `documents`, `document_items` |
| `audit-service` | `sqlite:////tmp/wms-audit.db` | `audit_events` |
| `reporting-service` | `sqlite:////tmp/wms-reporting.db` | `reporting_read_model_events`, `inventory_summary`, `document_summary`, `sales_summary`, `warehouse_activity_summary` |
| `ai-service` | `sqlite:////tmp/wms-ai.db` plus `/tmp/wms-ai-vector-db` | opt-in via the `ai` profile |

## Ownership Rules

- A service may write only its owned tables.
- Cross-service copies are read models, not source-of-truth tables.
- API Gateway remains the public REST entrypoint and does not own a datastore.
- `ai-service` stays opt-in for dev/test; include it explicitly with `docker compose --profile ai up -d`.

## Follow-up Work

- Phase L owns production migration tooling and service-owned seed/dev fixtures.
- Phase M owns transactional event publishing hardening for services that emit domain events.
- Phase O owns the final monolith archive/delete decision after active service fixtures and
  migrations are independent.
- Keep reporting/search read models behind explicit service-owned datastore connections.
