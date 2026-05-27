# WMS Monorepo (Microservices Refactor)

Repo này đã chuyển sang hướng microservices gRPC-first theo `MICROSERVICES_REFACTOR_PLAN.md`.
API Gateway là public REST entrypoint và gọi các service nội bộ qua gRPC.

## Roadmap

Trạng thái theo roadmap dài hạn: `docs/roadmap.md`

## Cấu trúc hiện tại

```
.
├── Services/
│   ├── api-gateway/        # (Scaffold ban đầu)
│   ├── identity-service/   # Identity gRPC
│   ├── customer-service/   # Customer gRPC
│   ├── product-service/    # Product gRPC
│   ├── warehouse-service/  # Warehouse gRPC
│   ├── inventory-service/  # Inventory gRPC
│   ├── documents-service/  # Documents gRPC
│   ├── audit-service/      # Audit gRPC + event consumer
│   ├── reporting-service/  # Reporting gRPC
│   ├── ai-service/         # AI gRPC, opt-in Compose profile
│   └── wms-monolith/       # Archived reference only, not default workspace/CI
└── Libraries/
    └── shared-utils/       # Shared library
```

## Monolith archive

`Services/wms-monolith/` đã được đóng băng thành archive tham chiếu. Nó không còn nằm trong
root `uv` workspace, CI mặc định, root compose, proto generation target, migration, fixture,
hoặc release workflow. Rollback reference tag: `phase-o-monolith-archive-exit`. Xem
`docs/monolith_retirement.md`.

## gRPC protos

- Protos đặt tại `proto/`
- Generate Python stubs (dùng venv trong repo): `./.venv/bin/python scripts/gen_protos.py`

## Phase 2

Chi tiết Phase 2 gRPC: `docs/phase2_grpc.md`

## Run (local)

Root `docker-compose.yml` không còn chạy `wms-monolith`. API public entrypoint là API Gateway:
- REST: `http://localhost:8000/api/v1/*`
- Downstream: gRPC nội bộ (identity/customer/product/warehouse/inventory)
- AI service được tách vào Compose profile `ai` để dev/test mặc định không build image ML nặng.

Chi tiết run: `docs/run_gateway.md`
