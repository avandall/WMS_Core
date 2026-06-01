# API Gateway

API Gateway là entry point HTTP công khai của hệ thống.

Env local/dev tối thiểu:
- `IDENTITY_GRPC_ADDR`
- `CUSTOMER_GRPC_ADDR`
- `PRODUCT_GRPC_ADDR`
- `WAREHOUSE_GRPC_ADDR`
- `INVENTORY_GRPC_ADDR`
- `DOCUMENTS_GRPC_ADDR`
- `AUDIT_GRPC_ADDR`
- `REPORTING_GRPC_ADDR`
- `AI_GRPC_ADDR`
- `GRPC_TIMEOUT_AI`
- `CORS_ORIGINS`
- `SECRET_KEY`

AI query đi qua `/api/v1/ai/query` và status đi qua `/api/v1/ai/status`, rồi gateway forward sang
AI service gRPC. Dashboard nên gọi gateway, không gọi trực tiếp các service nội bộ.
