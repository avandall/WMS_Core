# Warehouse Management System (WMS)

A modern warehouse management platform built as a gRPC-first microservices system. The codebase follows Clean Architecture, Domain-Driven Design (DDD), and service-owned data boundaries. It also integrates AI capabilities, event-driven messaging, observability, and Kubernetes deployment support.

## What this repository contains

- A **microservices architecture** with a dedicated API gateway and service runtimes.
- **Clean Architecture** boundaries separating transport, application, domain, and infrastructure.
- **Domain-Driven Design** for service ownership, aggregates, and bounded contexts.
- **Event-driven integration** using **Redis Streams**.
- **Observability** with **OpenTelemetry / OTLP**.
- **AI capabilities** via LangChain, ChromaDB, and model adapters.
- **Kubernetes examples** in `deploy/kubernetes`.

## Core Services

- `api-gateway` — API gateway, auth, validation, and request composition
- `identity-service` — identity, users, credentials, authorization
- `customer-service` — customer domain and service-owned customer data
- `product-service` — product catalog, SKUs, pricing, lifecycle rules
- `warehouse-service` — warehouses, locations, bins, capacity metadata
- `inventory-service` — inventory stock, reservations, movement ledger
- `documents-service` — document workflows, import/export, transfers
- `audit-service` — audit event append/read service
- `reporting-service` — projection read models and reporting
- `ai-service` — AI ingestion, retrieval, and generation pipelines
- `dashboard` — browser UI for operational views

## Architecture Overview

### Principles
- **Clean Architecture** with layered modules and explicit adapters.
- **DDD** with service-owned aggregates, repositories, and domain services.
- **Microservices** using gRPC for inter-service communication.
- **Event-driven design** using Redis Streams for async flows and decoupling.
- **Service-owned datastore** rules enforced by architecture and contract checks.

### Integration Patterns
- `gRPC` for synchronous service APIs.
- `Redis Streams` for async events and eventual consistency.
- **OpenTelemetry** for distributed tracing.
- **Service-specific `DATABASE_URL`** configuration for data separation.

## Technology Stack

- **Backend**: Python, FastAPI, gRPC
- **Data**: PostgreSQL (production), SQLite for local/test workflows
- **Messaging**: Redis Streams
- **AI / Vector Search**: LangChain, ChromaDB, OpenAI/Groq adapters
- **Containerization**: Docker, Docker Compose
- **Orchestration**: Kubernetes manifests in `deploy/kubernetes`
- **Observability**: OpenTelemetry / OTLP
- **Testing**: pytest, contract and integration tests
- **Packaging**: `pyproject.toml`, `requirements.txt`

## Local Development

### Prerequisites
- Docker and Docker Compose
- Python 3.11+ for local tooling and service development
- PostgreSQL for production-like datastore access, or SQLite for local/test execution

### Startup

1. Copy service environment examples and adjust settings:
   - `Services/api-gateway/.env.example`
   - `Services/identity-service/.env.example`
   - `Services/customer-service/.env.example`
   - ...
2. Configure service database URLs and secrets.
3. Start the core platform:

```bash
docker compose up -d api-gateway event-bus otel-collector identity-service customer-service product-service warehouse-service inventory-service documents-service audit-service reporting-service
```

4. If AI functionality is required, start the AI profile:

```bash
docker compose up -d --profile ai ai-service
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

## Key Capabilities

### Domain and Architecture
- Service boundaries defined by DDD ownership and data contracts
- Clean separation of domain, application, and infrastructure layers
- Repository pattern for persistence abstraction and testability
- Event contract rules enforced through docs and contract tests

### Infrastructure
- Redis Streams as the async event backbone
- PostgreSQL as primary relational storage
- Kubernetes manifests for deployment and platform portability
- OpenTelemetry tracing for distributed observability

### AI and Intelligence
- AI service for retrieval-augmented generation and custom query handling
- Vector search using ChromaDB
- Support for Groq, OpenAI, and local fine-tuned models

## Documentation

- `docs/architecture.md` — architecture decisions and service patterns
- `docs/data_ownership.md` — data ownership rules and service boundaries
- `docs/events.md` — event contract and Redis Streams guidance
- `deploy/kubernetes/README.md` — Kubernetes deployment guidance
- `proto/` — gRPC service contract definitions

## Contributing

1. Fork the repository
2. Create a feature branch
3. Respect service and domain boundaries
4. Add or update tests
5. Run `pytest`
6. Submit a pull request with a clear description

## Notes

- Active development targets the gRPC microservices runtime.
- The legacy monolith implementation is archived separately.
- Architecture guardrails prioritize service ownership, event-driven integration, and clean design.
