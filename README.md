# WMS Monorepo (Microservices Refactor)

Repo này đang được refactor từ monolith sang microservices theo `MICROSERVICES_REFACTOR_PLAN.md`.

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

Toàn bộ cách chạy cũ nằm trong `Services/wms-monolith/`.
