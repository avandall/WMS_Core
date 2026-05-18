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

## Monolith façade routing (REST → gRPC)

Monolith sẽ gọi gRPC services khi các env vars sau bật:

- `CUSTOMER_GRPC=1` và `CUSTOMER_GRPC_ADDR=customer-service:50052`
- `PRODUCT_GRPC=1` và `PRODUCT_GRPC_ADDR=product-service:50053`
- `WAREHOUSE_GRPC=1` và `WAREHOUSE_GRPC_ADDR=warehouse-service:50054`

Identity auth validation dùng:
- `IDENTITY_GRPC_ADDR=identity-service:50051`

