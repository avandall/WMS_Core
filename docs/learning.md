# Hướng Dẫn Học Refactor Monolith Sang Microservices: Phase 6 Trở Đi

File này viết lại quá trình refactor từ Phase 6 tới hiện tại theo góc nhìn học tập:
đọc từ đâu, hiểu điều gì trước, vì sao thay đổi được làm theo thứ tự đó, và khi tự làm lại
cần chú ý điểm nào.

Đây không phải tài liệu microservices chung chung. Nó bám vào chính repo này.

## Tư Duy Chính

Trước Phase 6, dự án đã có các service gRPC cơ bản. Từ Phase 6 trở đi, trọng tâm không còn
là “tách thêm service” nữa, mà là làm cho hệ thống mới thật sự vận hành như microservices:

- Có một public entrypoint rõ ràng: API Gateway.
- Các service backend nói chuyện bằng gRPC/protobuf.
- Dev/test chạy qua stack mới thay vì monolith.
- Mỗi service có datastore config riêng.
- Giao tiếp bất đồng bộ đi qua event bus.
- Observability, security, resilience, release, deployment được chuẩn hóa dần.
- Monolith bị đưa ra khỏi active workflow, chỉ còn làm archive tham chiếu.

Nói ngắn gọn:

```text
Monolith cũ: Client -> FastAPI monolith -> module nội bộ -> shared DB/runtime

Microservices mới:
Client
  -> API Gateway REST
  -> internal gRPC services
  -> service-owned datastore
  -> optional Redis Stream events
  -> async consumers/read models
```

Điều quan trọng nhất khi học giai đoạn này là: tách code chỉ là bước đầu. Phần khó hơn là
tạo lại các “đường ray vận hành” cho hệ thống mới: test, compose, tracing, security,
resilience, deployment, events, rollback.

## Giải Thích Code

Phần code trong repo này được tổ chức theo các lớp rõ ràng:

- API Gateway public boundary: `Services/api-gateway/src/api_gateway/main.py`,
  `app.py`, `routes.py`.
- gRPC client / downstream coupling: `Services/api-gateway/src/api_gateway/grpc_clients.py`.
- Observability/trace helpers: `Services/api-gateway/src/api_gateway/observability.py`.
- Auth/security boundary: `Services/api-gateway/src/api_gateway/auth.py` và
  `grpc_security.py`.
- Shared runtime helpers: `Libraries/shared-utils/src/shared_utils/` chứa
  event publisher, trace propagation, gRPC metadata, logging và security helpers.
- Mỗi backend service follow pattern: entrypoint server, `grpc_servicer.py`, application
  service layer, infrastructure repositories, and service-owned config.
- Event flow: producer dùng shared publisher trong `shared_utils/events/publisher.py`,
  publish vào Redis Streams, consumer group xử lý trong `Services/*/event_consumer.py`.
- Deployment/test flow: root `docker-compose.yml`, `deploy/kubernetes`,
  `tests/contract`, `tests/e2e`.

Đọc phần này trước khi xuống code giúp bạn hiểu “cái nào là entrypoint”, “cái nào là helper”,
“cái nào là runtime boundary”.

### 1. `README.md`

Đọc để hiểu repo hiện tại đang xem cái gì là “active system”.

Điểm cần nắm:

- Monolith cũ đã được tách sang branch `Monolith`, không còn là app chính của branch này.
- `Services/api-gateway` là public REST entrypoint.
- Các service như `identity-service`, `customer-service`, `inventory-service` là backend gRPC.
- AI service là opt-in, không nằm trong default dev/test.

### 2. `docs/roadmap.md`

Đọc để hiểu timeline. Đây là bản đồ tổng quát từ Phase 6 đến Phase 18.

Khi đọc, hãy chú ý cách roadmap chuyển trọng tâm:

- Phase 6-9: làm gateway và test stack mới chạy được.
- Phase 10-11: tách data ownership và event bus.
- Phase 12-14: production hardening.
- Phase 15-17: release/deployment/ops.
- Phase 18: async/read-model nâng cao.

### 3. `docs/run_gateway.md`

Đọc để hiểu cách chạy hệ thống mới.

Điểm cần nắm:

- User/client không gọi trực tiếp service backend.
- Client gọi API Gateway REST.
- Gateway gọi gRPC downstream.
- Docker compose mặc định không chạy AI.

### 4. `docker-compose.yml`

Đây là file rất đáng học. Nó cho thấy microservices chuyển từ ý tưởng thành runtime như thế nào.

Tìm các phần:

- `api-gateway`
- `identity-service`
- `customer-service`
- `event-bus`
- từng `DATABASE_URL` riêng
- `depends_on`
- `healthcheck`
- `profiles: ["ai"]`

Câu hỏi nên tự trả lời khi đọc:

- Service nào public port?
- Service nào chỉ nội bộ?
- Event bus nằm ở đâu?
- Vì sao AI không chạy mặc định?
- Mỗi service dùng DB config nào?

### 5. `Services/api-gateway/src/api_gateway/main.py`

Đây là cửa vào runtime mới.

Đọc để hiểu:

- middleware
- health/metrics
- security headers
- request id
- route mounting
- gateway làm public REST boundary như thế nào

### 6. `Services/api-gateway/src/api_gateway/grpc_clients.py`

Đây là file giúp hiểu gateway gọi gRPC ra sao.

Đọc để hiểu:

- tạo gRPC channel/stub
- truyền metadata như `x-request-id`, `traceparent`
- timeout/retry
- circuit breaker
- map lỗi downstream

Đây là nơi bạn thấy khác biệt rõ giữa monolith và microservices: trước đây gọi Python function
nội bộ, giờ gọi network boundary có timeout, lỗi mạng, retry, unavailable, deadline.

### 7. Một Service Đại Diện

Đọc `customer-service` trước vì dễ hiểu:

- `Services/customer-service/src/customer_service/grpc_server.py`
- `Services/customer-service/src/customer_service/grpc_servicer.py`
- `Services/customer-service/src/app/modules/customers/application/services/customer_service.py`
- `Services/customer-service/src/app/modules/customers/infrastructure/repositories/customer_repo.py`

Luồng cần hiểu:

```text
gRPC request
  -> grpc_servicer
  -> application service
  -> repository
  -> datastore
  -> protobuf response
```

Sau đó đọc service phức tạp hơn:

- `Services/documents-service/src/documents_service/grpc_servicer.py`
- `Services/inventory-service/src/inventory_service/grpc_servicer.py`
- `Services/audit-service/src/audit_service/event_consumer.py`
- `Services/reporting-service/src/reporting_service/event_consumer.py`

## Học Theo Từng Phase

### Phase 6: Làm API Gateway Thành Public Boundary

Mục tiêu:

```text
Client không gọi monolith hoặc service lẻ nữa.
Client gọi API Gateway.
Gateway gọi gRPC services.
```

Thay đổi quan trọng:

- API Gateway có REST endpoints `/api/v1/*`.
- Payload được chuẩn hóa bằng schema.
- Lỗi gRPC được map sang HTTP.
- Auth/rate limit/security middleware bắt đầu tập trung ở gateway.

Cần học:

- Gateway không nên chứa business logic sâu.
- Gateway nên làm:
  - auth/authz cơ bản
  - validation
  - routing
  - mapping REST/gRPC
  - error mapping
  - request id/tracing
- Service backend mới là nơi xử lý nghiệp vụ.

File nên đọc:

- `Services/api-gateway/src/api_gateway/main.py`
- `Services/api-gateway/src/api_gateway/routes.py`
- `Services/api-gateway/src/api_gateway/grpc_clients.py`
- `Services/api-gateway/src/api_gateway/schemas.py`

### Phase 7: Observability Và Reliability Cơ Bản

Mục tiêu:

Khi request đi qua nhiều service, phải trace/debug được.

Trong monolith, debug thường chỉ là một process log. Trong microservices, một request có thể đi:

```text
gateway -> identity -> customer -> event bus -> audit
```

Nếu không có request id/trace id, rất khó lần dấu.

Thay đổi quan trọng:

- Structured logs.
- `x-request-id`.
- `traceparent`.
- metrics endpoint.
- timeout/deadline policy.

File nên đọc:

- `docs/observability.md`
- `Libraries/shared-utils/src/shared_utils/observability/*`
- gateway middleware/interceptor liên quan tracing.

Điểm cần lưu ý:

- Microservices bắt buộc phải nghĩ về correlation id.
- Log đẹp chưa đủ; log phải nối được giữa service.

### Phase 8: Docker/Compose Chạy Thật

Mục tiêu:

Không chỉ có code service, mà phải chạy được service như một runtime riêng.

Thay đổi quan trọng:

- Root `Dockerfile`.
- Root `docker-compose.yml`.
- Service command như `api-gateway`, `identity-grpc`, `customer-grpc`.
- Healthcheck cho service.

File nên đọc:

- `Dockerfile`
- `docker-compose.yml`
- từng `Services/*/pyproject.toml`
- từng `Services/*/src/*/main.py`

Điểm cần học:

- Microservice không chỉ là folder tách riêng.
- Một service đúng nghĩa cần:
  - build được image riêng
  - có command riêng
  - có port riêng
  - có healthcheck
  - có env config riêng
  - có dependency runtime rõ ràng

### Phase 9: Chuyển Test Sang Gateway Stack

Mục tiêu:

Test phải bảo vệ luồng mới, không còn chỉ bảo vệ monolith.

Thay đổi quan trọng:

- Thêm gateway contract/E2E tests.
- Runner dựng stack tối thiểu bằng root compose.
- AI bị tách khỏi default test để không kéo dependency nặng.

File nên đọc:

- `tests/e2e/run_gateway_stack_tests.sh`
- `tests/e2e/*`
- `tests/contract/*`

Điểm cần học:

- Khi refactor từ monolith sang microservices, test phải đổi entrypoint.
- Nếu test vẫn gọi monolith, bạn có thể tưởng hệ thống mới ổn trong khi gateway/gRPC đã hỏng.
- E2E nên dựng vừa đủ service cho luồng quan trọng, không nhất thiết dựng toàn bộ stack nặng.

Lệnh quan trọng:

```bash
tests/e2e/run_gateway_stack_tests.sh
```

### Phase 10: Data Ownership

Mục tiêu:

Mỗi service phải có quyền sở hữu dữ liệu riêng. Đây là điểm rất quan trọng khi chuyển từ
monolith sang microservices.

Trong monolith, các module có thể cùng nhìn một database/schema. Trong microservices, nếu các
service vẫn join chung DB tùy ý thì thực chất chỉ là distributed monolith.

Thay đổi quan trọng:

- Compose cấp `DATABASE_URL` riêng cho từng service.
- Document table ownership.
- Audit service không còn phụ thuộc FK cross-service.
- Reporting/search được xem là read-model/duplication boundary.

File nên đọc:

- `docs/data_ownership.md`
- `docker-compose.yml`
- `tests/contract/test_compose_data_ownership.py`
- `tests/contract/test_service_data_boundaries.py`

Điểm cần học:

- Microservices chấp nhận duplicate data có kiểm soát.
- Không cross-service database join.
- Reporting nên đọc read model, không query database service khác.

### Phase 11-18: Tóm tắt thay đổi chính

- Phase 11: Thêm event bus/async workflow với Redis Streams, event envelope, publisher, và
  consumer audit/reporting/AI.
- Phase 12: Chuẩn hóa observability theo W3C `traceparent`, structured logs, metrics,
  và OTLP-ready compose baseline.
- Phase 13: Security hardening với explicit CORS, security headers, body limits, route-level
  rate limiting và opt-in gRPC mTLS.
- Phase 14: Resilience/SLO với gRPC timeout/deadline, bounded retry, circuit breaker, backpressure,
  và consumer failure guard.
- Phase 15: Release/Ops baseline với rollout/rollback contract, image/SBOM expectation,
  migration ownership và runbooks.
- Phase 16: Retire monolith khỏi active workflow, giữ archive reference và tập trung CI vào
  gateway/gRPC stack.
- Phase 17: Deployment automation với Kubernetes base manifests, secret placeholders,
  migration job examples và OTEL collector baseline.
- Phase 18: Advanced async/analytics workflows với durable consumer groups, DLQ/replay,
  reporting read-model consumer và opt-in AI reindex consumer.

### Phase 11: Event Bus

Mục tiêu:

Thay vì service gọi nhau đồng bộ cho mọi thứ, các sự kiện nghiệp vụ được publish vào event bus.

Thay đổi quan trọng:

- Redis Streams làm broker local.
- Event envelope có:
  - `event_id`
  - `schema_version`
  - `occurred_at`
  - `source`
  - `type`
  - `payload`
- Product/document/warehouse/inventory publish events.
- Audit service consume events.

File nên đọc:

- `docs/events.md`
- `Libraries/shared-utils/src/shared_utils/events/publisher.py`
- `Services/audit-service/src/audit_service/event_consumer.py`
- các `grpc_servicer.py` có gọi `get_publisher()`

Điểm cần học:

- Event không phải “log cho vui”; event là contract giữa service.
- `event_id` là idempotency key.
- Consumer phải chịu được duplicate/replay.

### Phase 12: Trace Context/OpenTelemetry Baseline

Mục tiêu:

Chuẩn hóa trace context theo W3C để sau này có thể nối với OpenTelemetry Collector.

Thay đổi quan trọng:

- Gateway nhận/tạo `traceparent`.
- Gateway truyền `traceparent` xuống gRPC metadata.
- gRPC services đọc metadata và log trace/span.
- Compose có OTLP env baseline.

File nên đọc:

- `docs/observability.md`
- `Libraries/shared-utils/src/shared_utils/observability/*`
- `docker-compose.yml`

Điểm cần học:

- Observability phải được thiết kế sớm.
- Sau khi tách service, “nó lỗi ở đâu?” là câu hỏi thường trực.

### Phase 13: Security Hardening

Mục tiêu:

Chuyển từ dev-friendly sang production-aware.

Thay đổi quan trọng:

- explicit CORS.
- security headers.
- request body limit.
- rate limit theo route/token/IP.
- gRPC mTLS opt-in qua env.
- secret không hardcode cho production.

File nên đọc:

- `docs/security.md`
- `Services/api-gateway/src/api_gateway/main.py`
- `Services/api-gateway/src/api_gateway/grpc_security.py`
- `Services/api-gateway/src/api_gateway/auth.py`
- `Libraries/shared-utils/src/shared_utils/security/*`

Điểm cần học:

- Internal gRPC plaintext có thể chấp nhận local/dev, nhưng production cần TLS/mTLS hoặc network policy/service mesh.
- Security không chỉ ở gateway, nhưng gateway là chỗ enforce public boundary đầu tiên.

### Phase 14: Resilience Và SLO

Mục tiêu:

Microservices phải chịu được downstream chậm/hỏng.

Trong monolith, function call fail thường là exception nội bộ. Trong microservices, có thêm:

- network timeout
- service unavailable
- deadline exceeded
- partial failure
- retry storm

Thay đổi quan trọng:

- timeout/deadline env.
- bounded retry cho idempotent calls.
- circuit breaker ở gateway.
- SLO baseline.
- backpressure cho event consumer.

File nên đọc:

- `docs/resilience.md`
- `Services/api-gateway/src/api_gateway/grpc_clients.py`
- `Services/audit-service/src/audit_service/event_consumer.py`

Điểm cần học:

- Không retry bừa.
- Chỉ retry call an toàn/idempotent.
- Circuit breaker giúp gateway fail nhanh thay vì treo toàn hệ thống.

### Phase 15: Release/Ops Baseline

Mục tiêu:

Hệ thống không chỉ chạy local, mà phải có câu chuyện release/rollback/ops.

Thay đổi quan trọng:

- image tagging strategy.
- SBOM expectation.
- rollout order.
- rollback order.
- migration ownership.
- runbooks.
- API/proto versioning.
- CI cleanup.

File nên đọc:

- `docs/release_ops.md`
- `.github/workflows/ci.yml`

Điểm cần học:

- Microservices cần rollout order.
- Gateway thường deploy cuối và rollback đầu.
- DB migration phải thuộc service owner.
- Proto field không được renumber/reuse.

### Phase 16: Retire Monolith Khỏi Active Workflow

Mục tiêu:

Khi stack mới đã đủ an toàn, không để monolith tiếp tục là “trọng tâm ngầm”.

Thay đổi quan trọng:

- Remove monolith khỏi root `uv` workspace.
- Remove monolith jobs khỏi default CI.
- Stop generate gRPC stubs vào monolith.
- Document monolith là archived reference only.

File nên đọc:

- `docs/monolith_retirement.md`
- `pyproject.toml`
- `scripts/gen_protos.py`
- `.github/workflows/ci.yml`

Điểm cần học:

- Nếu không retire monolith khỏi workflow, team sẽ tiếp tục sửa/test theo đường cũ.
- Archive là được, nhưng active build/test phải đi qua hệ thống mới.

### Phase 17: Deployment Automation

Mục tiêu:

Biến release contract thành deployment artifact thật.

Thay đổi quan trọng:

- Kubernetes base manifests.
- secret/cert placeholders.
- migration job examples.
- OpenTelemetry collector deployment.
- SLO alert examples.
- k3s local validation workflow.

File nên đọc:

- `deploy/kubernetes/README.md`
- `deploy/kubernetes/base/*`
- `deploy/kubernetes/examples/*`
- `tests/contract/test_deployment_automation_contract.py`

Điểm cần học:

- Compose tốt cho local/dev, nhưng production cần deployment package khác.
- Secret thật không commit.
- Manifest baseline cần validate được bằng `kubectl kustomize` và server dry-run.

Lệnh validate:

```bash
kubectl kustomize deploy/kubernetes/base
kubectl create namespace wms
kubectl apply -k deploy/kubernetes/base --dry-run=server
kubectl delete namespace wms
```

### Phase 18: Advanced Async/Analytics Workflows

Mục tiêu:

Hoàn thiện phần async/read-model còn deferred.

Thay đổi quan trọng:

- Shared durable Redis consumer group helper.
- Retry/reclaim bằng pending messages.
- DLQ streams.
- Audit consumer chuyển sang durable group.
- Reporting read-model consumer.
- AI reindex queue consumer opt-in.
- Replay tooling.

File nên đọc:

- `docs/events.md`
- `Libraries/shared-utils/src/shared_utils/events/publisher.py`
- `Services/audit-service/src/audit_service/event_consumer.py`
- `Services/reporting-service/src/reporting_service/event_consumer.py`
- `Services/ai-service/src/ai_service/event_consumer.py`
- `scripts/replay_events.py`
- `tests/contract/test_async_analytics_contract.py`

Điểm cần học:

- Async consumer phải idempotent.
- Message fail nhiều lần phải đi DLQ.
- Replay phải giữ metadata để kiểm tra idempotency.
- Reporting nên tiến dần về CQRS/read-model thay vì đọc lung tung operational data.

## Commit Timeline Để Học Theo Git

Nếu muốn xem từng bước bằng git, bắt đầu từ:

```bash
git show fe3c4a1
```

Các commit chính:

```text
fe3c4a1 phase 6
ce87bbf phase 7
0677a2a phase 7-2
95c21c5 phase 8
4b912de phase 8 update console script
16e849b phase 9 gateway contract e2e
9e9636e make ai service opt-in for dev
b55d685 use root compose for gateway e2e
c204356 Phase 10: isolate service datastore config
a86f800 Phase 10: complete data ownership baseline
b550746 Phase 11: add Redis event bus baseline
663ee1c Phase 12: add trace context propagation
ecf6376 Phase 13: add production security baseline
676cfb9 Phase 14: add resilience and SLO baseline
2ee2631 Phase 15: add release ops baseline
575386c Phase 16: retire monolith from active workflow
2af4e4c Phase 17: add deployment automation baseline
8d4c407 Phase 17: document k3s validation workflow
824b7f7 Phase 18: complete async analytics workflows
```

Cách học bằng commit:

```bash
git show --stat <commit>
git show <commit> -- docs/roadmap.md
git show <commit> -- docker-compose.yml
```

Với mỗi commit/phase, hãy tự hỏi:

- Phase này thay đổi runtime, test, data, security, hay deployment?
- File nào là entrypoint?
- Có contract test nào được thêm để khóa hành vi mới?
- AI có bị kéo vào default test/build không?
- Monolith có còn liên quan tới active workflow không?

## Những Điều Quan Trọng Cần Nhớ

### 1. Gateway Là Public Boundary

Không nên xem từng service backend là public API. User/client đi qua gateway.

Gateway chịu trách nhiệm:

- REST route
- auth/authz boundary
- request validation
- error mapping
- security headers
- trace/request id
- gọi gRPC downstream

Gateway không nên chứa business rule WMS sâu.

### 2. gRPC Là Internal Contract

Trong monolith, module gọi nhau bằng Python function. Sang microservices, gRPC là hợp đồng.

Cần chú ý:

- proto package/version
- timeout/deadline
- metadata propagation
- backward compatibility
- generated stubs

### 3. Test Phải Đi Qua Luồng Mới

Đây là điểm dễ sai khi refactor.

Nếu test vẫn bảo vệ monolith, bạn không biết gateway/gRPC stack có hỏng không.

Luồng test chính hiện tại:

```bash
tests/e2e/run_gateway_stack_tests.sh
```

Runner này dựng stack tối thiểu và chạy gateway contract/E2E.

### 4. Data Ownership Là Ranh Giới Microservices Thật

Tách service mà vẫn dùng chung DB tùy tiện thì chưa phải microservices đúng nghĩa.

Repo hiện tại đã có baseline:

- mỗi service có datastore config riêng
- audit/reporting/read model dùng duplication/event
- không thiết kế cross-service DB join làm đường chính

### 5. Event Là Contract, Không Phải Log Tùy Ý

Event hiện có envelope chuẩn:

```json
{
  "event_id": "uuid",
  "schema_version": 1,
  "occurred_at": "timestamp",
  "source": "documents-service",
  "type": "DocumentPosted",
  "payload": {}
}
```

`event_id` dùng để idempotency. Consumer phải chịu được duplicate và replay.

### 6. AI Phải Tách Khỏi Default Dev/Test

AI có dependency nặng, nên repo đã tách bằng Compose profile:

```bash
docker compose --profile ai up -d
```

Default test/dev không nên build hoặc install AI dependencies. Nếu một phase làm default test kéo
AI vào, đó là regression cần sửa.

### 7. Monolith Nằm Ngoài Branch Chạy Chính

Code cũ nằm ở branch `Monolith`; branch `gRPC` chỉ giữ runtime microservice. Vì vậy:

- không còn trong root `uv` workspace
- không còn trong CI mặc định
- không còn trong proto generation target
- không còn là app để contributor mới bắt đầu

## Lệnh Nên Biết Khi Review

Chạy gateway E2E:

```bash
tests/e2e/run_gateway_stack_tests.sh
```

Chạy contract tests:

```bash
env UV_CACHE_DIR=/tmp/uv-cache uv run --group dev pytest -q tests/contract
```

Validate compose:

```bash
docker compose config --quiet
```

Validate Kubernetes baseline:

```bash
kubectl kustomize deploy/kubernetes/base
kubectl create namespace wms
kubectl apply -k deploy/kubernetes/base --dry-run=server
kubectl delete namespace wms
```

Kiểm tra diff sạch trước commit:

```bash
git diff --check
git status --short
```

## Nên Review Kỹ Gì

- API Gateway:
  - route mapping
  - schemas
  - auth/security
  - gRPC error mapping
  - retry/circuit breaker

- Compose:
  - services mặc định
  - AI profile
  - datastore env
  - event bus
  - healthchecks

- Events:
  - event envelope
  - event publisher
  - consumer group
  - DLQ
  - replay

- Data ownership:
  - service nào sở hữu bảng nào
  - reporting/read model duplicate data ra sao

- CI/E2E:
  - có còn gọi monolith không
  - có kéo AI vào không
  - gateway stack có là safety net chính không

## Những Gì Vẫn Chưa Hoàn Hảo

Giai đoạn Phase 6-18 đã chuyển hệ thống sang microservices chạy được và có baseline vận hành.
Nhưng internal architecture của từng service vẫn còn dấu vết monolith:

- nhiều service có Clean Architecture/DDD-lite folder nhưng domain logic chưa thật sự giàu
- một số application service còn trả dict/ORM-ish object
- reporting còn cần tiến dần sang CQRS projection rõ hơn
- documents/inventory/warehouse nên được refactor DDD mạnh hơn
- CRUD service nên được làm gọn thay vì giữ abstraction rỗng

Kế hoạch tiếp theo nằm ở:

```text
docs/internal_architecture_refactor_plan.md
```

## Cách Tự Học Lại Theo Một Luồng Request

Ví dụ muốn hiểu luồng tạo/list customer:

1. Xem route trong API Gateway.
2. Xem schema request/response ở gateway.
3. Xem gateway client gọi gRPC method nào.
4. Xem proto tương ứng trong `proto/`.
5. Xem `customer_service/grpc_servicer.py`.
6. Xem application service.
7. Xem repository/model.
8. Chạy E2E test liên quan.

Tức là học theo đường:

```text
REST -> Gateway schema -> gRPC client -> proto -> gRPC servicer -> application -> repository -> DB
```

Ví dụ muốn hiểu async event:

1. Tìm service publish event bằng `get_publisher`.
2. Xem event envelope trong shared-utils.
3. Xem Redis Stream config trong compose.
4. Xem consumer trong audit/reporting/AI.
5. Xem DLQ/replay docs.
6. Xem contract test Phase 18.

Tức là học theo đường:

```text
producer service -> Redis Stream event -> durable consumer group -> datastore/read model/DLQ
```

## Tóm Tắt Một Câu

Từ Phase 6 trở đi, repo này chuyển trọng tâm từ “có các service tách ra” sang “microservices
vận hành được thật”: gateway là public boundary, gRPC là internal contract, compose/CI/test đi
theo stack mới, data/event/deployment được chuẩn hóa, và monolith bị đưa khỏi active workflow.
