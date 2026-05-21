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
| `audit-service` | `sqlite:////tmp/wms-audit.db` | none yet; table creation is blocked by legacy foreign keys to user/warehouse models |
| `reporting-service` | `sqlite:////tmp/wms-reporting.db` | `products`, `customers`, `warehouses`, `inventory`, `warehouse_inventory`, `documents`, `document_items`, `customer_purchases` |
| `ai-service` | `sqlite:////tmp/wms-ai.db` plus `/tmp/wms-ai-vector-db` | opt-in via the `ai` profile |

## Ownership Rules

- A service may write only its owned tables.
- Cross-service copies are read models, not source-of-truth tables.
- API Gateway remains the public REST entrypoint and does not own a datastore.
- `ai-service` stays opt-in for dev/test; include it explicitly with `docker compose --profile ai up -d`.

## Remaining Phase 10 Work

- Replace legacy cross-domain repository writes with gRPC calls or events.
- Add per-service migrations instead of runtime `create_all`.
- Remove foreign keys that point across service ownership boundaries.
- Build reporting/search read models from events instead of direct DB coupling.
