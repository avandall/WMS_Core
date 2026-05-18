# WMS Microservices Refactor Plan

## 1. Overview
This project currently lives as a monolithic FastAPI application with a clear domain module structure under `src/app/modules` and a separate AI engine in `src/ai_engine`.

The recommended microservice decomposition preserves business capabilities, minimizes coupling, and makes it easier to scale individual domains, data stores, and AI-specific workloads.

## 2. Target Service Set
The new architecture should consist of the following services:

1. **API Gateway / Edge Service**
2. **Identity Service**
3. **Customer Service**
4. **Product Catalog Service**
5. **Warehouse Service**
6. **Inventory Service**
7. **Documents Service**
8. **Audit Service**
9. **Reporting Service**
10. **AI / Knowledge Service**

Additionally, a shared library package should hold common DTOs, auth helpers, logging, and configuration utilities.

## 3. Service Responsibilities

### 3.1 API Gateway / Edge Service
- Expose the public REST API surface.
- Route requests to downstream services.
- Enforce authentication, authorization, CORS, rate limiting, and request validation.
- Aggregate data for composite endpoints when needed.
- Return a consistent API contract to clients.

Suggested responsibilities:
- `/api/v1/auth/*` (proxy to Identity Service)
- `/api/v1/users/*` (proxy to Identity Service)
- `/api/v1/customers/*` (proxy to Customer Service)
- `/api/v1/products/*` (proxy to Product Catalog Service)
- `/api/v1/warehouses/*` (proxy to Warehouse Service)
- `/api/v1/inventory/*` (proxy to Inventory Service)
- `/api/v1/documents/*` (proxy to Documents Service)
- `/api/v1/audit-events/*` (proxy to Audit Service)
- `/api/v1/reports/*` (proxy to Reporting Service)
- `/api/v1/ai/*` (proxy to AI Service)

### 3.2 Identity Service
- Own user accounts, authentication, authorization, and positions/roles.
- Issue JWTs or API tokens.
- Validate credentials and session state.
- Manage user profile, roles, positions, and permissions.
- Provide user lookup for other services.

Likely endpoints:
- `POST /auth/login`
- `POST /auth/refresh`
- `GET /users/me`
- `GET /users/{id}`
- `POST /users`
- `PATCH /users/{id}`
- `GET /positions`
- `POST /positions`

### 3.3 Customer Service
- Own customer master data.
- Manage customer lifecycle and customer metadata.
- Handle customer-specific business rules.
- Emit domain events when customer data changes.

Likely endpoints:
- `GET /customers`
- `GET /customers/{id}`
- `POST /customers`
- `PATCH /customers/{id}`

### 3.4 Product Catalog Service
- Own product definitions, SKUs, units, and product metadata.
- Manage product lifecycle and uploads.
- Provide product search, details, and metadata.
- Support integration with inventory and warehouse services.

Likely endpoints:
- `GET /products`
- `GET /products/{id}`
- `POST /products`
- `PATCH /products/{id}`
- `POST /products/{id}/upload`

### 3.5 Warehouse Service
- Own warehouse definitions, locations, and storage structures.
- Manage warehouse configuration and capacity metadata.
- Handle warehouse-specific operations and location management.
- Provide warehouse metadata for inventory, routing, and AI.

Likely endpoints:
- `GET /warehouses`
- `GET /warehouses/{id}`
- `POST /warehouses`
- `PATCH /warehouses/{id}`
- `GET /warehouses/{id}/operations`

### 3.6 Inventory Service
- Own stock levels, reservations, movements, and allocations.
- Manage inventory transactions and positioning.
- Handle goods receipt, issuing, adjustments, and inventory reconciliation.
- Provide stock reporting and availability.

Likely endpoints:
- `GET /inventory`
- `GET /inventory/{sku}`
- `POST /inventory/adjust`
- `POST /inventory/move`
- `POST /inventory/reserve`

### 3.7 Documents Service
- Own documents, attachments, metadata, and document search.
- Handle upload, retrieval, indexing, and storage references.
- Support document-related operations used by other services.
- Provide document content to the AI service.

Likely endpoints:
- `GET /documents`
- `GET /documents/{id}`
- `POST /documents`
- `PATCH /documents/{id}`
- `DELETE /documents/{id}`

### 3.8 Audit Service
- Own audit event storage and retrieval.
- Capture cross-service actions for compliance and traceability.
- Support filtering, query, and retention policies.
- Optionally receive events from the API Gateway or as messages from other services.

Likely endpoints:
- `GET /audit-events`
- `POST /audit-events/search`

### 3.9 Reporting Service
- Own report generation and aggregated analytics.
- Build read models and dashboards from events and snapshots.
- Support historical queries and reporting-specific filters.
- Consume domain events from other services.

Likely endpoints:
- `GET /reports/overview`
- `GET /reports/inventory`
- `GET /reports/warehouse-utilization`
- `GET /reports/customer-activity`

### 3.10 AI / Knowledge Service
- Own the AI engine, retrieval, LLM generation, and agent logic in `src/ai_engine`.
- Host vector store, embedding generation, and RAG orchestration.
- Expose query endpoints for both direct question answering and tool-driven agent use.
- Integrate with domain services to resolve inventory, product, warehouse, and document queries.

Likely endpoints:
- `POST /ai/query`
- `POST /ai/agent-query`
- `POST /ai/reindex`
- `GET /ai/status`

## 4. Data Ownership & Persistence

Each service should own its own persistence layer and schema. Recommended boundaries:

- Identity Service: `users`, `positions`, `roles`, `tokens`
- Customer Service: `customers`
- Product Catalog Service: `products`, `product_metadata`
- Warehouse Service: `warehouses`, `warehouse_locations`, `warehouse_operations`
- Inventory Service: `inventory_items`, `stock_levels`, `inventory_transactions`
- Documents Service: `documents`, `document_metadata`
- Audit Service: `audit_records`
- Reporting Service: materialized views, aggregated metrics, report caches
- AI Service: vector store, embeddings, knowledge index, AI logs

### Recommended persistence mode
- Prefer separate logical databases or schemas per service.
- Use separate database connections to enforce autonomy.
- For the AI Service, use a vector store or dedicated embedding database separate from relational data.

## 5. Integration Patterns

### 5.1 Synchronous API calls
- For direct lookup and command workflows, call one service from another using REST/gRPC.
- Use the API Gateway as the public entry point.
- Keep synchronous chains short.

### 5.2 Event-driven communication
- Publish domain events whenever state changes.
- Use a message broker such as RabbitMQ, Kafka, NATS, or Redis Streams.
- Ideal events:
  - `CustomerCreated`
  - `CustomerUpdated`
  - `ProductCreated`
  - `ProductUpdated`
  - `WarehouseCreated`
  - `InventoryAdjusted`
  - `DocumentUploaded`
  - `AuditEventLogged`
- Subscribe services for eventual consistency:
  - Reporting Service consumes most domain events.
  - Audit Service can ingest event payloads or store forwarded audit logs.
  - AI Service consumes document and metadata change events to refresh indexes.

### 5.3 Shared schema use cases
- Avoid direct database access across services.
- Prefer API or event-based sharing over foreign key joins.
- Only allow shared libraries for common validation and contract definitions.

## 6. Migration Roadmap

### Phase 0: Preparation
1. Create a shared library package for common models and utilities.
2. Isolate existing domain modules into service-shaped folders.
3. Identify all public API endpoints in `src/app/api/v1/endpoints`.
4. Define service contracts and Swagger/OpenAPI schemas.

### Phase 1: Extract Identity Service
1. Move `auth`, `users`, `positions`, and authorization logic into a new Identity Service.
2. Build authentication middleware as a reusable component.
3. Change the monolith to call the Identity Service for auth/permission checks.
4. Confirm user management works through the new service.

### Phase 2: Extract Product, Customer, and Warehouse Domains
1. Extract `customers` into Customer Service.
2. Extract `products` into Product Catalog Service.
3. Extract `warehouses` and `warehouse_operations` into Warehouse Service.
4. Keep the monolith as a façade while routing those endpoints to the new services.

### Phase 3: Extract Inventory and Documents
1. Extract `inventory` into Inventory Service.
2. Extract `documents` into Documents Service.
3. Introduce event publication for inventory changes and document uploads.
4. Ensure the new services can call Identity Service for auth and Product/Warehouse services for metadata when needed.

### Phase 4: Extract Audit and Reporting
1. Create Audit Service and migrate audit event storage.
2. Create Reporting Service and move report generation logic.
3. Use event-driven ingestion from other services.

### Phase 5: Extract AI Engine
1. Convert `src/ai_engine` into a standalone AI Service.
2. Implement an interface for other services to query AI.
3. Sync documents, products, warehouses, and inventory metadata into the AI Service through events or API fetch.
4. Add AI service health checks and separate configuration.

### Phase 6: Harden the API Gateway
1. Deploy the API Gateway as the only external entry point.
2. Migrate clients to the gateway.
3. Enable observability, logging, tracing, and API versioning.
4. Remove any remaining direct client access to internal services.

## 7. Deployment & Infra Recommendations

### 7.1 Containerization
- Build each service with its own `Dockerfile`.
- Use a root `docker-compose.yml` or Kubernetes manifests for local/integration testing.
- Keep container images small and explicit.

### 7.2 Networking
- Use service names and internal DNS for inter-service communication.
- Secure internal traffic with mTLS or network policies where possible.

### 7.3 Observability
- Centralize logs with structured JSON.
- Add distributed tracing for cross-service calls.
- Monitor request latency, error rates, and event processing metrics.

### 7.4 Configuration
- Keep service-specific config in environment files or a config service.
- Use consistent settings naming across services.
- Do not share secret or DB config between services.

## 8. Recommended Repository Layout

For a monorepo-style refactor:

```
/Services
  /api-gateway
  /identity-service
  /customer-service
  /product-service
  /warehouse-service
  /inventory-service
  /documents-service
  /audit-service
  /reporting-service
  /ai-service
/Libraries
  /shared-models
  /shared-utils
/infra
  /docker
  /k8s
  /observability
/tests
  /integration
  /contract
  /end-to-end
```

## 9. Cross-cutting concerns

- **Security**: centralize auth in Identity Service and enforce at the API Gateway.
- **Validation**: use shared DTO definitions for contract compatibility.
- **Telemetry**: instrument each service for logs, metrics, and traces.
- **Testing**: provide service-level unit tests, contract tests, and end-to-end tests.
- **Versioning**: expose stable versioned APIs, especially for shared services.

## 10. Key Architecture Decisions

- Do not split too aggressively. Keep services aligned with business capabilities.
- Use a message broker for cross-service data replication and reporting.
- Preserve the AI engine as its own service because its data and compute needs are distinct.
- Keep audit and reporting services read-only from other domains and driven by events.

## 11. Practical next step
- Start by creating the `Identity Service` and `API Gateway`.
- Extract one domain at a time, verify with feature tests, and keep the monolith as a temporary façade.
- Refactor shared code into reusable libraries rather than shared databases.

---

This plan is intended to turn the existing monolith into a set of domain-aligned, independently deployable services while preserving the current WMS feature set and supporting future scaling of AI and analytics. 