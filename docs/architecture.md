# Architecture

This document describes the active architecture on the `gRPC` branch. The runtime system is
gRPC-first microservices behind an API Gateway. The retired monolith source lives on branch
`Monolith`; this branch contains only the active service runtime and supporting artifacts.

## Service Patterns

| Service | Pattern | Owns | Does not own |
| --- | --- | --- | --- |
| `api-gateway` | BFF/API composition | REST routes, auth, validation, request IDs, tracing, gRPC error mapping | WMS business rules or data tables |
| `identity-service` | Lightweight Clean Architecture | users, credentials, token policy, roles/permissions | warehouse positions or operational WMS data |
| `customer-service` | CRUD + application service | customers and customer-owned history | product, document, inventory, warehouse source-of-truth data |
| `product-service` | Catalog CRUD + light domain rules | products, SKUs, catalog lifecycle | inventory stock or warehouse structure |
| `warehouse-service` | Tactical DDD where useful | warehouses, locations, bins, capacity/status metadata | stock movement, reservations, documents |
| `inventory-service` | Tactical DDD + use cases | stock, reservations, movement ledger, idempotency | product catalog or warehouse source-of-truth data |
| `documents-service` | Tactical DDD + aggregate workflow | documents, document items, lifecycle state | product/customer/warehouse source-of-truth repositories |
| `audit-service` | Event append/read service | audit event records | operational aggregates |
| `reporting-service` | CQRS/read-model projections | projection tables and event idempotency ledger | operational repositories |
| `ai-service` | Pipeline/adapters | opt-in ingestion, retrieval, generation, provider adapters | default dev/test flows or operational databases |

## Dependency Rules

- `domain` contains entities, value objects, domain services, domain exceptions, and repository
  interfaces. It must not import `application`, `infrastructure`, FastAPI, gRPC, SQLAlchemy
  sessions, Redis clients, or generated protobuf modules.
- `application` coordinates use cases and accepts command/query DTOs. It may depend on domain
  interfaces and shared application abstractions, but not transport DTOs or concrete adapters.
- `infrastructure` implements repositories, database models, event bus clients, provider clients,
  and other adapters.
- `grpc` and HTTP adapter packages map transport messages to application commands/queries and map
  errors back to transport responses.
- Generated protobuf Python files under service `gen/` packages are transport artifacts. Change
  contracts in `proto/wms/*/v1` and regenerate with `scripts/gen_protos.py`.

## Data Ownership

Service-owned data remains mandatory. A service may write only its owned tables. If another
service needs that data, use one of these shapes:

- gRPC lookup by ID for synchronous workflows.
- Event-updated read model for reporting/search/query-heavy workflows.
- Immutable snapshot stored with an aggregate, such as document line product/customer metadata.

The current `docs/data_ownership.md` file is the datastore baseline. During Phase B, non-owned
modules and tables in active services should be converted to ports, gRPC clients, snapshots, or
explicit read models.

## Event Contracts

Redis Streams is the async integration backbone. Events use the shared envelope from
`shared_utils.events` with `event_id`, `schema_version`, `occurred_at`, `source`, `type`, and
`payload`.

- Producers must publish service-owned facts.
- Consumers must tolerate additive payload fields.
- Duplicate `event_id` and replay metadata must be idempotent.
- Breaking changes require a new event type or a versioned consumer path.

`docs/events.md` is the event baseline and must stay aligned with producer/consumer tests.

## Active Refactor Guardrails

Phase A guardrails apply only to active services on this branch.
They should:

- fail when domain code imports transport or infrastructure concerns;
- fail when application use cases import transport DTOs or concrete runtime clients;
- prevent new non-owned modules or DB tables from being added before Phase B cleans up the
  current baseline;
- keep AI outside default dev/test/build flows.
