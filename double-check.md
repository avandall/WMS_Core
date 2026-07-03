1. Walkthrough
This PR introduces a multi-phase document lifecycle (approve, reserve, release, start-execution, confirm, complete) and an inventory reservation/transaction ledger system, wired through updated protos, gRPC servicers, gateway routes/UI, and reporting projections. It also standardizes CORS settings validation across services, removes database_url validation, adds local orchestration tooling, and deletes numerous legacy shared_utils modules and contract tests.

Estimated code review effort: 5 (Critical) | ~120 minutes

Changes
Document Lifecycle and Inventory Ledger Feature

Layer / File(s)	Summary
Proto contracts
proto/wms/documents/v1/documents.proto, proto/wms/inventory/v1/inventory.proto	New RPCs and message types for document approve/reserve/execute/complete phases and inventory availability/reservation/transaction ledger.
Document domain and schema
Services/documents-service/.../domain/*, .../infrastructure/models/document*.py, migrations/phase6_*.sql	New TransactionType/ReasonCode/status enums, transaction mapping, extended Document/DocumentProduct entities, new model columns, migration.
Document service and repository
Services/documents-service/.../document_service.py, document_repo.py	New reserve/release/start-execution/confirm/complete workflow logic and persistence of lifecycle fields; deprecates post_document.
Documents gRPC servicer
Services/documents-service/src/documents_service/grpc_servicer.py	New RPC handlers for approval/reservation/execution phases, transaction metadata passthrough.
Inventory domain and schema
Services/inventory-service/.../domain/*, infrastructure/models/*, migrations/phase2/4/9_*.sql	StockBalance value object, reservation/ledger interface methods, new ORM models and quantity-matrix columns.
Inventory repository and service
Services/inventory-service/.../inventory_repo.py, inventory_service.py	Reservation lifecycle, available-stock computation, transaction ledger persistence and service orchestration.
Inventory gRPC servicer
Services/inventory-service/src/inventory_service/grpc_servicer.py	New RPCs for availability, reservation listing/release, transaction listing, confirm inventory transaction.
API gateway routes/schemas/presenters
Services/api-gateway/src/api_gateway/routes.py, schemas.py, presenters.py	Login endpoint, document workflow and inventory endpoints, new payload schemas, extended document/item fields.
Dashboard UI
dashboard/index.html, dashboard/script.js, dashboard/README.md	Transaction sub-type/reason-code UI, confirm-execution modal, quantity matrix display, workflow action buttons.
AI query templates
Services/ai-service/src/ai_service/pipeline/templates.py	New keyword patterns and intent mappings for inventory/document ledger queries.
Reporting projections
Services/reporting-service/.../projections.py, read_model_repo.py	New warehouse_matrix/executed_quantity columns and event projection logic for lifecycle and ledger events.
Gateway app proxy
Services/api-gateway/src/api_gateway/app.py	Dashboard static file serving and dev auth/backend proxy route.
Settings validators, deployment tooling, and legacy cleanup

Layer / File(s)	Summary
Settings validator changes
Services/*/src/app/shared/core/settings.py	Removes database_url validation, adds CORS string-to-list validator across eight services.
Deployment tooling and dependencies
run_all.py, secret.txt, requirement_render.txt, requirements.txt	New local orchestration entrypoint, config templates, rewritten dependency list.
Shared utils removal and test cleanup
README.md, tests/conftest.py, shared_utils/*, tests/contract/*.py	Path updates, removal of shared_utils events/observability modules, new legacy-compat test, removal of many legacy contract tests.
Sequence Diagram(s)

1.1 Verify each finding against current code. Fix only still-valid issues, skip the
rest with a brief reason, keep changes minimal, and validate.

In `@Services/api-gateway/src/api_gateway/routes.py` around lines 57 - 93, The
login_auth endpoint is still using a hardcoded dev_users credential map and a
fallback SECRET_KEY, so replace that local authentication flow with the existing
identity-service login delegation used by the gateway. Update login_auth to fail
closed when the JWT secret is missing instead of defaulting to
replace-with-render-secret, and keep token creation only after a successful
identity-service response using the existing jwt/os/datetime flow.

1.2. Verify each finding against current code. Fix only still-valid issues, skip the
rest with a brief reason, keep changes minimal, and validate.

In `@Services/api-gateway/src/api_gateway/routes.py` around lines 760 - 796, Move
the reason-code validation in confirm_document_execution ahead of the
documents_stub().ConfirmExecution call, using the already fetched doc fields
(doc_type, tx_type, and doc.reason_code) to decide whether ADJUSTMENT_IN,
ADJUSTMENT_OUT, SCRAP, or INTERNAL_CONSUMPTION requires a reason code. If the
reason code is missing, raise the HTTPException before mutating the document so
the ConfirmExecution mutation only runs after all preconditions pass.

1.3 Verify each finding against current code. Fix only still-valid issues, skip the
rest with a brief reason, keep changes minimal, and validate.

In
`@Services/documents-service/src/app/modules/documents/application/services/document_service.py`
around lines 272 - 301, The StockReserved flow in document_service.py is
publishing a reservation event before any real inventory reservation exists,
while the loop over document.items only mutates the in-memory document and
fabricates reservation IDs. Update the reservation path in the document
execution method so it calls the real inventory reservation API/port, enforces
ATP, and obtains actual reservation IDs before setting item reserved_qty,
marking execution_started_at, saving, and publishing StockReserved. Use the
existing document_repo.save, _commit_if_needed, and event_publisher.publish flow
only after the inventory side has successfully created reservations.

1.4 Verify each finding against current code. Fix only still-valid issues, skip the
rest with a brief reason, keep changes minimal, and validate.

In
`@Services/documents-service/src/app/modules/documents/application/services/document_service.py`
around lines 397 - 428, Validate the confirmation payload in document_service.py
before setting document.status to EXECUTED inside the execution-confirm flow.
Add checks in the method that handles the confirmed items to reject empty items,
duplicate product_id values, unknown product_ids not present in document.items,
missing expected lines, and quantities outside the allowed requested/reserved
range before any save or publish. Use the existing item_map and items loop in
DocumentService to enforce these validations, and only proceed to persist and
emit WarehouseExecutionConfirmed after the payload matches the document lines.

1.5 Verify each finding against current code. Fix only still-valid issues, skip the
rest with a brief reason, keep changes minimal, and validate.

In `@Services/inventory-service/migrations/phase4_add_stock_reservations.sql`
around lines 20 - 31, The stock reservation migration defines uniqueness twice
and uses invalid PostgreSQL syntax for partial uniqueness. In the
stock_reservations migration, update the end-of-file uniqueness definitions to
use CREATE UNIQUE INDEX with WHERE clauses instead of CREATE UNIQUE CONSTRAINT,
and remove the inline UNIQUE from idempotency_key so the uniqueness is only
declared once. Refer to the stock_reservations table definition and the
uq_stock_reservation_idempotency / uq_stock_reservation_source statements when
making the fix.

2. ## Issue description
The gateway implements a hardcoded login flow (`dev_users`) and JWT issuance under `/api/auth/login`.

## Issue Context
This bypasses any real user store by accepting fixed passwords and creates JWTs inside the gateway.

## Fix Focus Areas
- Remove the hardcoded `dev_users` login/identity endpoints from the gateway
- If a demo-mode is required, gate it behind an explicit env flag AND disable by default
- Prefer delegating authentication to identity-service (or a dedicated auth module)

### Fix Focus Areas (code)
- Services/api-gateway/src/api_gateway/app.py[107-145]
- Services/api-gateway/src/api_gateway/auth.py[28-69]

3. ## Issue description
The refresh endpoint is implemented as an echo of the provided token, not a refresh operation.

## Issue Context
The gateway uses bearer tokens widely; refresh should either be removed or should validate the token and issue a new one with a fresh `exp`.

## Fix Focus Areas
- Either remove `/api/auth/refresh` and update clients accordingly
- Or implement refresh: validate the token, then issue a new JWT with a new expiry

### Fix Focus Areas (code)
- Services/api-gateway/src/api_gateway/app.py[147-153]

4. ## Issue description
An async route uses blocking `urllib.request.urlopen()`.

## Issue Context
Blocking I/O in the event loop degrades throughput and can stall concurrent requests.

## Fix Focus Areas
- Replace `urlopen()` with an async HTTP client (e.g., `httpx.AsyncClient`) OR avoid self-HTTP proxying entirely by routing internally
- Add timeouts and preserve relevant headers

### Fix Focus Areas (code)
- Services/api-gateway/src/api_gateway/app.py[210-242]

5. ## Issue description
The proxy overwrites `Content-Type` and maps a CSV upload endpoint to a JSON-only backend endpoint.

## Issue Context
Dashboard uploads a file via `FormData` to `/api/products/import-csv`, but gateway maps it to `/api/v1/products` and forces JSON content-type.

## Fix Focus Areas
- Preserve incoming `Content-Type` and forward the request body/headers faithfully (including multipart boundaries)
- Implement a real `/api/v1/products/import-csv` backend endpoint that accepts multipart upload, OR change the dashboard to parse CSV and POST JSON to `/api/products`

### Fix Focus Areas (code)
- Services/api-gateway/src/api_gateway/app.py[203-223]
- Services/api-gateway/src/api_gateway/routes.py[318-336]
- dashboard/script.js[3413-3424]