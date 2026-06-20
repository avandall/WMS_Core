# WMS Hybrid Core Architecture And Refactor Plan

## 1. Executive Summary

`WMS_Core` should move from "pure microservices with one database per service" to a hybrid
architecture:

- one shared relational database for core operational WMS modules;
- separate databases/stores for audit, reporting, AI, events, cache, and future heavy workloads;
- service/process boundaries kept at first, with an explicit later decision on whether to collapse
  the core into one modular `core-service`.

This is the best fit for the current WMS domain because inventory, documents, products,
warehouses, customers, and users are not loosely related. They are part of the same operational
transaction surface. Forcing them through separate databases creates unnecessary eventual
consistency, extra gRPC calls, duplicate read models, and slow joins.

The target is not a return to an uncontrolled monolith. It is an Odoo-style modular core with clear
module ownership, shared ACID transactions where they matter, and isolated services where
independence still creates value.

## 2. Architecture Decision

### 2.1 Chosen Model

Use three persistence zones.

| Zone | Persistence | Modules | Why |
| --- | --- | --- | --- |
| Core operational DB | One shared relational database | identity/users, customers, products, warehouses/positions/locations, inventory, documents | Strong consistency, joins, foreign keys, one transaction for critical WMS workflows |
| Independent read/history DBs | Separate service-owned databases | audit, reporting/read models | Append-only, analytical, rebuildable, different retention and scale |
| Specialist stores | Separate stores | AI metadata/vector DB, Redis Streams, object/blob storage, search/cache if added | Optional or specialized workloads should not slow core operations |

### 2.2 Why Identity And Documents Belong In The Core DB

The older hybrid draft kept identity and documents separate. That is reasonable for generic
microservices, but suboptimal for this WMS system.

Identity should be in the core DB because:

- `users`, positions, approvals, created-by, posted-by, and cancelled-by are part of operational
  records;
- permission-sensitive workflows need fast lookup;
- user references should be enforceable and easy to join in audit-friendly screens.

Documents should be in the core DB because:

- document posting is the main workflow that changes inventory;
- document line items need product, warehouse, customer, and user context;
- posting and inventory movement should commit together where possible;
- document status should not become eventually consistent with stock.

Document files/blobs can still live outside the core DB later. The operational document metadata
and line items should be core.

## 3. Target Runtime Components

| Component | Keep as process initially? | Persistence target | Role |
| --- | --- | --- | --- |
| `api-gateway` | Yes | None | Public REST/BFF, auth enforcement, validation, tracing, error mapping |
| `identity-service` | Yes initially | Core DB | Users, auth policy, permissions, user references |
| `customer-service` | Yes initially | Core DB | Customer master data and operational customer history |
| `product-service` | Yes initially | Core DB | Products, SKUs, catalog lifecycle |
| `warehouse-service` | Yes initially | Core DB | Warehouses, positions, locations, capacity/status metadata |
| `inventory-service` | Yes initially | Core DB | Stock, reservations, movement ledger, idempotency |
| `documents-service` | Yes initially | Core DB | Documents, line items, lifecycle state, posting/cancellation workflow |
| `audit-service` | Yes | Audit DB | Compliance event store from outbox/Redis events |
| `reporting-service` | Yes | Reporting DB | CQRS projections and summaries |
| `ai-service` | Yes, opt-in | AI DB/vector store | RAG, embeddings, indexing, AI pipelines |
| Redis Streams | Yes | Redis | Event fanout, replay, DLQ, external integration |

After the shared core DB is stable, evaluate whether the six core services should remain separate
processes or be merged into one `core-service`.

## 4. Core Database Ownership

The database is shared, but write ownership remains strict.

| Module | Owns tables |
| --- | --- |
| Identity | `users`, future `roles`, `permissions`, `user_roles`, `sessions`, `tokens` if stored |
| Customer | `customers`, `customer_purchases` if operational, future addresses/contacts |
| Product | `products`, future variants/categories/units/metadata |
| Warehouse | `warehouses`, `positions`, future locations/bins/zones |
| Inventory | `inventory`, `warehouse_inventory`, `inventory_movement_ledger`, future reservations |
| Documents | `documents`, `document_items` |
| Core platform | `core_outbox`, `schema_migrations`, optional `idempotency_keys` |

Separate stores:

| Module | Owns |
| --- | --- |
| Audit | `audit_events` in audit DB |
| Reporting | projection tables and `reporting_read_model_events` in reporting DB |
| AI | AI metadata DB, vector DB, local model cache, reindex queue |
| Event bus | Redis streams and DLQs |

## 5. Governance Rules

- Each table has exactly one owning module.
- Only the owning module writes its tables directly.
- Other core modules may read through approved query services, SQL joins, views, or foreign keys.
- Cross-module writes happen through application use cases, not random repository calls.
- Critical workflows may share one database transaction.
- Audit, reporting, AI, and integrations consume outbox/events and never write core tables.
- Schema changes are versioned in one core migration layer.
- Generated protobuf files and transport adapters remain outside domain/application logic.
- The API Gateway does not own WMS business rules.

For Postgres production, prefer schemas for clarity:

```text
wms_core
├── identity.*
├── customer.*
├── product.*
├── warehouse.*
├── inventory.*
├── documents.*
└── platform.*
```

For SQLite local/dev, use table naming or metadata ownership because SQLite does not support
schemas in the same way.

## 6. Decision Matrix For Future Modules

Put a module in the core DB when most of these are true:

- it participates in operational WMS transactions;
- users expect immediate consistency;
- it needs joins with inventory, documents, products, warehouses, customers, or users;
- foreign keys would prevent real business errors;
- failure to update together creates inconsistent stock or document state.

Keep a module separate when most of these are true:

- it is append-only history, reporting, search, AI, cache, or integration data;
- eventual consistency is acceptable;
- the data can be rebuilt from core data or events;
- it needs a different storage engine, retention policy, or scaling profile;
- it should remain optional in local/dev/test.

## 7. Target Data And Transaction Patterns

### 7.1 Core Reads

Use direct relational reads for high-value core screens:

- inventory by warehouse with product names;
- document detail with customer, warehouse, product, and approval user;
- stock availability by product and warehouse;
- movement history by document, product, warehouse, and user.

Avoid gRPC fanout for data that is already in the same core DB.

### 7.2 Core Writes

Use one transaction for workflows that must be immediately consistent.

Example: document posting

1. Load document, customer, warehouse, product, user, and stock rows from the core DB.
2. Validate document lifecycle, permissions, and stock movement rules.
3. Update `documents`, `document_items`, `inventory`, `warehouse_inventory`, and
   `inventory_movement_ledger`.
4. Insert `core_outbox` event rows in the same transaction.
5. Commit.
6. Outbox publisher emits events to Redis Streams for audit, reporting, AI, and integrations.

This replaces "document emits event, inventory eventually applies movement" as the required core
consistency path. Events still exist, but they are for fanout and external consistency, not for the
core stock/document commit.

### 7.3 Cross-Database Workflows

Use events or Saga-style compensation only when a workflow crosses out of the core DB, for example:

- indexing documents into AI;
- writing compliance history to audit DB;
- updating reporting projections;
- syncing external systems;
- storing or deleting physical files in object storage.

## 8. Target Infrastructure

### 8.1 Database Configuration

Introduce:

- `CORE_DATABASE_URL` for identity, customer, product, warehouse, inventory, and documents;
- `AUDIT_DATABASE_URL` or existing `DATABASE_URL` for audit;
- `REPORTING_DATABASE_URL` or existing `DATABASE_URL` for reporting;
- AI-specific config for AI DB/vector store.

Local compose should eventually have:

- one `core-data` volume;
- one `audit-data` volume;
- one `reporting-data` volume;
- existing Redis/event-bus;
- AI profile remaining opt-in.

### 8.2 Migration Layer

Use one ordered core migration entrypoint, for example `core-migrate`.

The migration layer should:

- create all core tables;
- encode table ownership metadata;
- apply foreign keys and indexes;
- prevent duplicate table ownership;
- be runnable against a clean database and existing migrated data;
- be separate from audit/reporting/AI migrations.

### 8.3 Transactional Outbox

Add `core_outbox` to the core DB.

Recommended fields:

- `id`
- `event_id`
- `event_type`
- `schema_version`
- `aggregate_type`
- `aggregate_id`
- `source_module`
- `payload`
- `status`
- `attempt_count`
- `last_error`
- `created_at`
- `published_at`

The outbox publisher emits to Redis Streams after DB commit and supports retry/replay.

## 9. Refactor Roadmap

### Phase 0: Align Architecture And Guardrails

Goal: make the hybrid target explicit and testable.

- Mark identity, customers, products, warehouses/positions, inventory, and documents as core DB
  participants.
- Mark audit, reporting, AI, Redis/event bus, and future search/blob stores as separate.
- Replace strict "one service, one DB" tests with hybrid ownership tests.
- Add tests that fail when a non-core service writes core tables.
- Add tests that fail when two modules claim the same core table.
- Update architecture/data ownership/event docs.

Acceptance:

- Docs and tests agree on the three persistence zones.
- The old separate-database rule is no longer active for core modules.
- Ownership guardrails are enforced in CI.

### Phase 1: Add Shared Core DB Config Without Behavior Changes

Goal: let all core services connect to one DB while preserving current APIs.

- Add `CORE_DATABASE_URL`.
- Add a local compose override or direct compose change with one shared core DB.
- Point identity/customer/product/warehouse/inventory/documents at `CORE_DATABASE_URL`.
- Keep audit/reporting/AI separate.
- Ensure each service still initializes or migrates only owned tables.

Acceptance:

- Gateway stack starts with one shared core DB.
- Existing public API behavior remains compatible.
- Audit and reporting still use separate DBs.

### Phase 2: Create The Core Migration Layer

Goal: remove per-service schema creation races.

- Add `core-migrate`.
- Move core table creation into ordered migrations.
- Add ownership metadata.
- Add required foreign keys and indexes.
- Disable or simplify per-service `LOCAL_DB_BOOTSTRAP_ENABLED` for core tables.

High-priority indexes:

- inventory by `product_id`;
- warehouse inventory by `warehouse_id`, `product_id`;
- documents by `doc_type`, `status`, `customer_id`, `warehouse_id`;
- document items by `document_id`, `product_id`;
- movement ledger by `source_event_id`, `document_id`, `product_id`, `warehouse_id`.

Acceptance:

- A clean core DB is created by one command.
- Core service startup does not race on table creation.
- Migration tests validate tables, indexes, and foreign keys.

### Phase 3: Consolidate DB Session Infrastructure

Goal: remove duplicated DB plumbing across core services.

- Move shared SQLAlchemy engine/session setup into `Libraries/shared-utils` or
  `Libraries/core-db`.
- Standardize transaction helpers.
- Add test helpers for one temporary core DB.
- Keep repositories module-owned.

Acceptance:

- Core services use the same DB/session implementation.
- Tests can create one temporary core DB for cross-module workflows.

### Phase 4: Optimize Core Read Paths

Goal: remove unnecessary service fanout for relational data.

- Identify N+1 gRPC/API lookups.
- Replace them with approved core query services or SQL joins.
- Keep public REST/gRPC contracts stable.
- Add tests for joined read responses.

First read paths:

- document detail with joined customer, warehouse, user, and product line data;
- inventory by warehouse with product names;
- stock availability by product/warehouse.

Acceptance:

- Core reads no longer need chained gRPC calls for basic joins.
- Response compatibility is preserved.
- Query ownership is documented.

### Phase 5: Move Critical Workflows To Shared Transactions

Goal: fix the real consistency pain.

- Refactor document posting and inventory movement into one core DB transaction.
- Keep idempotency through `inventory_movement_ledger` or shared `idempotency_keys`.
- Convert `InventoryMovementRequested` from required internal consistency event to optional
  post-commit notification or remove it after consumers migrate.
- Review and migrate:
  - goods receipt;
  - sale/issue;
  - stock adjustment;
  - reservation/release;
  - warehouse transfer;
  - document cancellation/reversal.

Acceptance:

- Document state and stock movement cannot commit separately.
- Duplicate posting remains idempotent.
- E2E document/inventory workflows pass against shared DB.

### Phase 6: Add Transactional Outbox And Event Fanout

Goal: keep audit/reporting/AI reliable without making Redis part of core consistency.

- Add `core_outbox`.
- Write outbox rows in the same transaction as core state changes.
- Add publisher worker.
- Publish existing event contracts where possible.
- Update audit/reporting/AI consumers if event names or payloads change.
- Keep replay and DLQ behavior.

Acceptance:

- Crash after core commit but before Redis publish is recoverable.
- Outbox publish is idempotent.
- Audit/reporting/AI receive events after commit.

### Phase 7: Migrate Existing Data And Cut Over

Goal: move current separate core DBs into the shared DB safely.

- Inventory source tables, row counts, indexes, constraints, and IDs.
- Build migration scripts from:
  - identity DB;
  - customer DB;
  - product DB;
  - warehouse DB;
  - inventory DB;
  - documents DB.
- Preserve IDs where possible.
- Add ID mapping if collisions exist.
- Validate row counts, checksums, foreign keys, and sample workflows.
- Rehearse on copied data.
- Back up all service DBs before cutover.
- Keep old DBs read-only until verification is complete.

Acceptance:

- Migration is repeatable from backups.
- Validation proves core integrity.
- Rollback is documented and tested.

### Phase 8: Decide Process Consolidation

Goal: decide whether to keep hybrid microservices or move to a modular monolith core.

Keep separate core processes if:

- independent deploys are still valuable;
- ownership boundaries matter;
- gRPC overhead is acceptable after shared DB consolidation;
- operational isolation is useful.

Collapse to one `core-service` if:

- most workflows cross several core services;
- deployment complexity remains high;
- cross-module transactions become the norm;
- the desired direction is explicitly Odoo-like modular monolith.

If collapsing:

- create `Services/core-service/src/app/modules/*`;
- move identity, customer, product, warehouse, inventory, and documents modules into it;
- keep API Gateway as the public edge;
- retire internal gRPC calls between core modules;
- keep event/outbox fanout for audit/reporting/AI/integrations.

Acceptance:

- A decision record explains the chosen runtime.
- The chosen runtime has fewer moving parts than the current baseline.

### Phase 9: Cleanup And Documentation

Goal: remove obsolete strict-microservice leftovers.

- Remove old per-core-service DB volumes/config.
- Remove obsolete per-service core migration commands.
- Delete consumers that only existed to synchronize immediate core state.
- Keep events for audit, reporting, AI, integrations, notifications, and replay.
- Update docs, compose, Kubernetes manifests, runbooks, and tests.

Acceptance:

- New developers can run the core with one operational DB.
- No duplicate source of truth remains for core operational data.
- Every separate store has an explicit reason.

## 10. Migration Order

Recommended order:

1. Product
2. Warehouse
3. Customer
4. Identity
5. Documents
6. Inventory
7. Cross-module document posting/inventory transaction

Reasoning:

- product and warehouse are low-risk reference data;
- customer and identity add references needed by documents;
- documents should move before inventory transaction refactor;
- inventory moves last because it carries the highest consistency and idempotency risk.

## 11. Testing Strategy

Minimum per phase:

- migration tests for schema, indexes, and foreign keys;
- repository tests against one temporary core DB;
- ownership tests for allowed writers and forbidden writers;
- event/outbox contract tests;
- API Gateway contract tests for public behavior;
- E2E gateway stack tests for core workflows;
- `docker compose config --quiet` for compose changes.

Critical regression workflows:

- login and permission check;
- create customer/product/warehouse;
- receive stock;
- reserve/release stock;
- create and post sale document;
- cancel/reverse document if supported;
- list inventory by warehouse with product details;
- document detail with customer/product/warehouse/user data;
- audit receives post-commit events;
- reporting projections update from events;
- AI remains opt-in and is not required by default tests.

## 12. Deployment And Operations

### 12.1 Core DB HA

For production, use Postgres or another managed relational DB with:

- primary/replica or managed HA;
- point-in-time recovery;
- automated backups;
- tested restore procedure;
- connection pooling;
- slow query monitoring;
- lock/deadlock monitoring.

SQLite is acceptable only for local/dev/test unless the deployment is intentionally single-node.

### 12.2 Observability

Track:

- core DB connection pool usage;
- slow queries by module;
- lock waits and deadlocks;
- transaction latency;
- outbox publish lag;
- Redis consumer lag and DLQ counts;
- API latency by endpoint;
- migration duration and failures.

### 12.3 Security

- Use separate DB credentials per runtime component where possible.
- In Postgres, enforce schema/table privileges for module ownership.
- Use TLS for database and service-to-service traffic in production.
- Rotate credentials through the platform secret manager.
- Audit privileged DB operations and schema migrations.
- Keep API Gateway as the public auth/authz enforcement point.

## 13. Risks And Controls

| Risk | Control |
| --- | --- |
| Shared DB becomes uncontrolled coupling | table ownership tests, schema privileges, documented query services |
| Core DB becomes single point of failure | HA, backups, PITR, restore drills |
| Long transactions block operations | transaction review, indexes, lock monitoring |
| SQLite hides production behavior | Postgres integration/staging tests |
| Migration causes ID conflicts | migration rehearsal, ID mapping, validation reports |
| Reporting overloads core DB | reporting DB remains separate and event-fed |
| Events drift from committed data | transactional outbox |
| Service startup races on schema | one core migration entrypoint |
| Too many core processes remain complex | Phase 8 process consolidation decision |

## 14. Recommended First Implementation Slice

Do this before committing to the full refactor:

1. Add `CORE_DATABASE_URL` and a compose override that points all core services to one local DB.
2. Add core table ownership metadata and guardrail tests.
3. Add `core-migrate` for the current core tables.
4. Run existing gateway E2E tests against the shared DB without changing behavior.
5. Optimize one read path with a direct join.
6. Refactor document posting plus inventory movement into one shared transaction.
7. Add `core_outbox` and publish audit/reporting events after commit.

If this slice reduces complexity and improves latency without breaking ownership rules, continue
through the full roadmap.

## 15. Success Criteria

Functional:

- core WMS operations work through one operational DB;
- inventory and document state remain immediately consistent;
- no duplicate source of truth for core data;
- audit/reporting/AI still receive events.

Performance:

- fewer internal calls for joined core reads;
- lower latency for document and inventory workflows;
- core DB handles expected load without lock contention.

Operational:

- migrations are repeatable;
- rollback is documented;
- monitoring covers DB, outbox, Redis, and API behavior;
- new developers can understand the persistence zones quickly.

## 16. Final Target

The final architecture should feel like this:

- modular-monolith data consistency for the core WMS domain;
- microservice-style isolation for audit, reporting, AI, and external integration;
- one source of truth for operational records;
- event-driven fanout after commit;
- explicit ownership rules that keep the shared DB disciplined.
