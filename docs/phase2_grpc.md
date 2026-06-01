# Phase 2 (gRPC-first) - Customer/Product/Warehouse

Phase 2 đã extract các domain sau khỏi monolith và expose bằng gRPC:

## Ports

- Identity gRPC: `identity-service:50051` (ValidateToken)
- Customer gRPC: `customer-service:50052`
- Product gRPC: `product-service:50053`
- Warehouse gRPC: `warehouse-service:50054`

## Proto files

- `proto/wms/customer/v1/customer.proto`
- `proto/wms/product/v1/product.proto`
- `proto/wms/warehouse/v1/warehouse.proto`

## Generate stubs (Python)

`./.venv/bin/python scripts/gen_protos.py`

## Public routing

Monolith façade đã được loại khỏi root `docker-compose.yml` và khỏi default workspace/CI.
Public entrypoint chuyển sang API Gateway (`Services/api-gateway/`) và gateway sẽ gọi gRPC services.
