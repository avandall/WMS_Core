# Service Template

Use the smallest template that fits the service. Do not add layers because another service has
them; add a folder only when it owns real behavior.

## BFF/API Composition Service

Used by `api-gateway`.

```text
<gateway>/
  routes.py
  clients.py
  errors.py
  auth.py
  tracing.py
  gen/
```

Rules:

- Owns transport routing, auth, validation, tracing, request IDs, and error mapping.
- Calls service gRPC APIs through client adapters.
- Does not contain WMS business rules or database models.

## CRUD/Application Service

Used by `customer-service`, `product-service`, and parts of `identity-service`.

```text
src/
  <service>_service/
    grpc_server.py
    grpc_servicer.py
    app.py
    gen/
  app/
    modules/<owned-module>/
      application/
        dtos/
        services/
      domain/
        entities/
        exceptions/
        interfaces/
      infrastructure/
        models/
        repositories/
    shared/
```

Rules:

- Keep application services thin and explicit.
- Keep domain folders only when there are real rules, invariants, or interfaces.
- Put SQLAlchemy models/repositories in infrastructure.

## Tactical DDD Service

Used by `documents-service`, `inventory-service`, and focused parts of `warehouse-service`.

```text
src/
  <service>_service/
    grpc_server.py
    grpc_servicer.py
    app.py
    gen/
  app/
    modules/<owned-module>/
      domain/
        entities/
        value_objects/
        events/
        exceptions/
        interfaces/
      application/
        commands/
        queries/
        handlers/
        dtos/
      infrastructure/
        models/
        repositories/
        event_publishers/
```

Rules:

- Domain owns state transitions and invariants.
- Application owns transaction/use-case orchestration.
- Transport adapters only translate requests and responses.

## Event Consumer Service

Used by `audit-service` and by projection consumers.

```text
src/
  <service>_service/
    event_consumer.py
    grpc_server.py
    grpc_servicer.py
  app/
    modules/<owned-module>/
      application/
      domain/
      infrastructure/
```

Rules:

- Consume Redis Stream envelopes through durable consumer groups.
- Acknowledge events only after service-owned persistence succeeds.
- Write failed events to a service-owned DLQ after retry policy is exhausted.

## Read-Model Service

Used by `reporting-service`.

```text
src/
  reporting_service/
    event_consumer.py
    grpc_server.py
    grpc_servicer.py
  app/
    modules/reporting/
      application/
        queries/
        projection_handlers/
      infrastructure/
        models/
        repositories/
```

Rules:

- Query projection tables, not operational repositories.
- Keep an idempotency ledger keyed by event ID.
- Rebuild projections from `wms.events` or `wms.events.replay`.

## AI Pipeline Service

Used by `ai-service`.

```text
src/
  ai_service/
    event_consumer.py
    grpc_server.py
    grpc_servicer.py
  ai_engine/
    ingestion/
    indexing/
    retrieval/
    generation/
    providers/
```

Rules:

- Stay behind the opt-in compose/runtime profile.
- Consume events or read-model snapshots, not operational databases.
- Keep heavy AI dependencies out of default contract and E2E test flows.
