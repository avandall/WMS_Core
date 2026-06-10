# Warehouse Management System (WMS)

A modern warehouse orchestration platform built as a gRPC-first Python microservices system. This repository follows Clean Architecture, Domain-Driven Design (DDD), service-owned data boundaries, event-driven messaging, and AI-enhanced warehouse intelligence.

## Repository Overview

- **Microservices architecture** with an API gateway and dedicated service runtimes.
- **Clean Architecture** separating transport, application, domain, and infrastructure layers.
- **DDD** with bounded contexts, aggregates, domain services, and repository abstractions.
- **Event-driven integration** using **Redis Streams** for async workflows.
- **Observability** via **OpenTelemetry / OTLP**.
- **AI capabilities** with LangChain, ChromaDB, and provider adapters.
- **Kubernetes deployment examples** in `deploy/kubernetes`.

## Core Services

- `api-gateway` — unified REST/façade, auth, validation, request composition
- `identity-service` — identity, users, authentication, authorization
- `customer-service` — customer domain and service-owned customer data
- `product-service` — product catalog, SKUs, pricing, lifecycle rules
- `warehouse-service` — warehouses, locations, bins, capacity metadata
- `inventory-service` — inventory stock, reservations, movement ledger
- `documents-service` — document workflow, import/export, transfers
- `audit-service` — append/read audit event service
- `reporting-service` — read-model projections and analytics
- `ai-service` — AI ingestion, retrieval, generation, and vector search
- `dashboard` — browser-based operational UI

## Architecture and Patterns

### Design principles
- **Clean Architecture** with explicit adapter boundaries and layered dependencies.
- **Domain-Driven Design** with service ownership, aggregates, and rich domain logic.
- **Microservices** with gRPC service contracts and independent deployable units.
- **Service-owned data** ensures each service controls its own datastore and schema.
- **Event-driven architecture** using Redis Streams for decoupled asynchronous flows.
- **API gateway** as a composition layer for client-facing APIs.

### Integration patterns
- `gRPC` for service-to-service communication.
- `Redis Streams` for event publishing, consumer replay, and async coordination.
- `OpenTelemetry` for distributed tracing and observability.
- `DATABASE_URL` per service to enforce isolated datastore connections.

## Technology Stack

- **Language**: Python 3.11+
- **Web/API**: FastAPI, gRPC
- **Database**: PostgreSQL (production), SQLite for local/test flows
- **Messaging**: Redis Streams
- **AI / Vector Search**: LangChain, ChromaDB, OpenAI/Groq adapters
- **Containerization**: Docker, Docker Compose
- **Orchestration**: Kubernetes manifests under `deploy/kubernetes`
- **Observability**: OpenTelemetry / OTLP
- **Testing**: pytest, contract, integration, security, and e2e tests
- **Packaging**: `pyproject.toml`, `requirements.txt`

## Local Development

### Prerequisites
- Docker and Docker Compose
- Python 3.11+ for local tooling
- PostgreSQL for production-like datastore access, or SQLite for local/test execution

### Startup

1. Copy service environment examples and configure secrets:
   - `Services/api-gateway/.env.example`
   - `Services/identity-service/.env.example`
   - `Services/customer-service/.env.example`
   - `Services/product-service/.env.example`
   - `Services/warehouse-service/.env.example`
   - `Services/inventory-service/.env.example`
   - `Services/documents-service/.env.example`
   - `Services/audit-service/.env.example`
   - `Services/reporting-service/.env.example`
   - `Services/ai-service/.env.example`

2. Configure each service `DATABASE_URL` or service-specific database secret.
3. Start the platform:

```bash
docker compose up -d api-gateway event-bus otel-collector identity-service customer-service product-service warehouse-service inventory-service documents-service audit-service reporting-service
```

4. Start AI support when required:

```bash
docker compose --profile ai up -d ai-service
```

### Local URLs

- API Gateway: `http://localhost:8000`
- Dashboard: `http://localhost:8080`
- OpenTelemetry Collector: `http://localhost:4317`
- Redis event bus: `localhost:6379`

## Running Tests

```bash
pytest
```

## Project Layout

- `Services/` — microservice packages and source code
- `dashboard/` — UI assets and dashboard application
- `deploy/` — Kubernetes manifests and deployment examples
- `docs/` — architecture, governance, events, and operations documentation
- `proto/` — Protobuf service contract definitions
- `scripts/` — dev tooling, seeding, migrations, replay, and validation
- `shared_utils/` — cross-service shared libraries and helpers
- `tests/` — unit, integration, contract, security, and e2e tests

## Documentation

- `docs/architecture.md` — architecture decisions and service patterns
- `docs/data_ownership.md` — service data ownership and repository boundaries
- `docs/events.md` — event contract rules and Redis Streams guidance
- `deploy/kubernetes/README.md` — Kubernetes deployment and config guidance
- `proto/` — gRPC service definitions and contract sources

## Contributing

1. Fork the repository
2. Create a feature branch
3. Respect service and domain boundaries
4. Add or update tests
5. Run `pytest`
6. Submit a pull request with a clear description

## Notes

- Active development targets the gRPC microservices runtime.
- The legacy monolith is archived separately and is not part of active development.
- Architecture guardrails prioritize service ownership, event-driven integration, and clean design.
