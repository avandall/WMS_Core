# Run via API Gateway (REST → gRPC)

## 1) Generate gRPC stubs

`./.venv/bin/python scripts/gen_protos.py`

## 2) Start stack

Root compose exposes the API Gateway at `http://localhost:8000`.

`docker compose up -d`

## 3) Notes

- Identity gRPC is used for token validation (`ValidateToken`).
- Services currently have both REST and gRPC scaffolds, but the intended public surface is API Gateway REST.
- Phase 3 adds Inventory + Documents gRPC services and exposes them via API Gateway:
  - `/api/v1/inventory/*`
  - `/api/v1/documents/*`

- Phase 4 adds Audit + Reporting gRPC services:
  - `/api/v1/audit-events/*`
  - `/api/v1/reports/*`

- Phase 5 adds AI gRPC service:
  - `/api/v1/ai/*`
