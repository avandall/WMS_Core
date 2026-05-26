# AI Service

AI / Knowledge Service chạy opt-in qua compose profile `ai`.

Phạm vi:
- AI engine, RAG, embeddings, agent logic
- gRPC query endpoint + health/metrics HTTP endpoint
- Event-driven reindex queue từ domain events hoặc projection snapshots

Runtime mặc định của dự án không build/start service này. Khi cần AI:

```bash
docker compose --profile ai up -d ai-service
```

Pipeline boundary:

- `ai_service.pipeline.ingestion`: đổi event envelope/snapshot thành reindex job.
- `ai_service.pipeline.indexing`: queue adapter AI-owned cho reindex job.
- `ai_service.pipeline.retrieval`: boundary cho retrieval context.
- `ai_service.pipeline.generation`: query pipeline.
- `ai_service.pipeline.providers`: adapter vào RAG/LLM engine nặng.

AI không đọc database vận hành của service khác; dữ liệu vào phải đến từ event hoặc read-model
snapshot có thể replay.
