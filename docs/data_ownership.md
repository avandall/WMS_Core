# Data Ownership Baseline

Phase 10 starts the move from a monolith-shaped shared schema to service-owned datastores.

## Local Compose Strategy

Root `docker-compose.yml` now gives every service its own datastore connection instead of inheriting one shared `DATABASE_URL`.

| Service | Local datastore | Tables initialized today |
| --- | --- | --- |
| `identity-service` | `sqlite:////tmp/wms-identity.db` | `users` |
| `customer-service` | `sqlite:////tmp/wms-customer.db` | `customers` |
| `product-service` | `sqlite:////tmp/wms-product.db` | `products`, `inventory` |
| `warehouse-service` | `sqlite:////tmp/wms-warehouse.db` | `products`, `warehouses`, `warehouse_inventory`, `positions`, `inventory`, `position_inventory` |
| `inventory-service` | `sqlite:////tmp/wms-inventory.db` | `products`, `warehouses`, `inventory`, `warehouse_inventory` |
| `documents-service` | `sqlite:////tmp/wms-documents.db` | `products`, `customers`, `warehouses`, `documents`, `document_items` |
| `audit-service` | `sqlite:////tmp/wms-audit.db` | `audit_events` |
| `reporting-service` | `sqlite:////tmp/wms-reporting.db` | `products`, `customers`, `warehouses`, `inventory`, `warehouse_inventory`, `documents`, `document_items`, `customer_purchases` |
| `ai-service` | `sqlite:////tmp/wms-ai.db` plus `/tmp/wms-ai-vector-db` | opt-in via the `ai` profile |

## Ownership Rules

- A service may write only its owned tables.
- Cross-service copies are read models, not source-of-truth tables.
- API Gateway remains the public REST entrypoint and does not own a datastore.
- `ai-service` stays opt-in for dev/test; include it explicitly with `docker compose --profile ai up -d`.

## Follow-up Work

- Replace remaining legacy read-model refreshes with event consumers in Phase 11.
- Add production migration tooling before deployment.
- Keep reporting/search read models behind explicit service-owned datastore connections.
