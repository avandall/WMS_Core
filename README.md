# WMS Monorepo (Microservices Refactor)

Repo này đang được refactor từ monolith sang microservices theo `MICROSERVICES_REFACTOR_PLAN.md`.
Inter-service communication chuẩn hóa bằng gRPC (API Gateway sẽ làm REST→gRPC).

## Cấu trúc hiện tại

```
.
├── Services/
│   ├── api-gateway/        # (Scaffold ban đầu)
│   ├── identity-service/   # (Scaffold ban đầu)
│   ├── customer-service/   # (Placeholder)
│   ├── product-service/    # (Placeholder)
│   ├── warehouse-service/  # (Placeholder)
│   ├── inventory-service/  # (Placeholder)
│   ├── documents-service/  # (Placeholder)
│   ├── audit-service/      # (Placeholder)
│   ├── reporting-service/  # (Placeholder)
│   ├── ai-service/         # (Placeholder)
│   └── wms-monolith/       # Toàn bộ code monolith hiện tại
└── Libraries/
    └── shared-utils/       # Shared library (scaffold ban đầu)
```

## Chạy monolith (tạm thời)

Monolith chỉ còn dùng để tham chiếu code/so sánh và chạy test guard. Entrypoint chạy chính thức là `Services/api-gateway/`.

## gRPC protos

- Protos đặt tại `proto/`
- Generate Python stubs (dùng venv trong repo): `./.venv/bin/python scripts/gen_protos.py`

## Phase 2

Chi tiết Phase 2 gRPC + monolith façade routing: `docs/phase2_grpc.md`

## Run (local)

Root `docker-compose.yml` không còn chạy `wms-monolith`. API public entrypoint là API Gateway:
- REST: `http://localhost:8000/api/v1/*`
- Downstream: gRPC nội bộ (identity/customer/product/warehouse/inventory)
