# Core Business Transaction Refactor Plan

## 1. Problem Summary

`docs/issue.md` identifies a real WMS business gap: the current system treats warehouse movement
as one generic flow:

```text
Create document -> Approve/Post document -> Add/subtract inventory
```

That is too narrow for real business operations. SAP, MISA, Odoo, and ERP/WMS systems separate the
business reason for movement, reservation/allocation, warehouse execution, and accounting/audit
evidence.

The current code confirms this issue:

- `DocumentType` only has `IMPORT`, `EXPORT`, `TRANSFER`, `SALE`.
- `DocumentStatus` only has `DRAFT`, `POSTED`, `CANCELLED`.
- `DocumentService.post_document()` marks a document as `POSTED` and publishes
  `InventoryMovementRequested`.
- `InventoryService.apply_document_movement()` applies physical stock based on document lines.
- `InventoryService.reserve_stock()` exists, but it only records a movement event. It does not
  persist `reserved_qty`, does not reduce ATP, and does not prevent double-selling.
- `inventory` and `warehouse_inventory` store only one `quantity` value.
- API Gateway exposes `/documents/{id}/post` as the main operational action.
- Dashboard shows a single `Approve & Post` button for draft documents.

The target is to refactor WMS core business logic from generic document posting into transaction
type driven warehouse operations.

## 2. Target Business Model

Use four separate concepts.

| Concept | Meaning | Updates physical stock? |
| --- | --- | --- |
| Business request | A document/order/request created by office, sales, purchasing, production, or warehouse planning | No |
| Reservation/allocation | Blocks available stock for an outbound/transfer/production issue | No, but reduces available-to-promise |
| Execution confirmation | Warehouse confirms actual received, picked, shipped, transferred, scrapped, or counted quantity | Yes |
| Inventory ledger | Immutable evidence of every stock-affecting movement | Already applied result |

The system should no longer assume `approve == stock movement`.

Recommended lifecycle:

```text
DRAFT
  -> REQUESTED
  -> RESERVED/PARTIALLY_RESERVED, where applicable
  -> IN_PROGRESS
  -> EXECUTED/PARTIALLY_EXECUTED
  -> COMPLETED

Any pre-completion state can go to CANCELLED.
Completed movements can be reversed with a reversal transaction, not edited/deleted.
```

## 3. Transaction Types

Replace broad `doc_type` behavior with explicit `transaction_type` and optional `reason_code`.

### 3.1 Inbound

| Transaction type | Business meaning | Source reference |
| --- | --- | --- |
| `PURCHASE_RECEIPT` | Receive goods from supplier | Purchase order or supplier document |
| `PRODUCTION_RECEIPT` | Receive finished goods from production | Work order |
| `SALES_RETURN_RECEIPT` | Receive returned goods from customer | Sales return/RMA |
| `TRANSFER_RECEIPT` | Receive stock from another warehouse | Transfer order |
| `ADJUSTMENT_IN` | Increase stock after count/adjustment | Count session/reason |

### 3.2 Outbound

| Transaction type | Business meaning | Source reference |
| --- | --- | --- |
| `SALES_SHIPMENT` | Ship goods to customer | Sales order |
| `PRODUCTION_ISSUE` | Issue materials to production | Work order/BOM |
| `PURCHASE_RETURN_SHIPMENT` | Return goods to supplier | Purchase return |
| `TRANSFER_ISSUE` | Ship stock to another warehouse | Transfer order |
| `INTERNAL_CONSUMPTION` | Internal use | Department/cost center |
| `SCRAP` | Scrap/destroy stock | Scrap reason |
| `ADJUSTMENT_OUT` | Decrease stock after count/adjustment | Count session/reason |

### 3.3 Transfer

Transfers should be two-step:

1. `TRANSFER_ISSUE`: source warehouse confirms dispatch and moves stock to `in_transit_qty`.
2. `TRANSFER_RECEIPT`: destination warehouse confirms receipt and moves stock from in-transit to
   physical stock.

This prevents stock from disappearing globally while goods are in transit.

## 4. Inventory Quantity Model

Replace single quantity with a matrix.

At minimum:

| Field | Meaning |
| --- | --- |
| `physical_qty` | Real stock physically in a warehouse/bin |
| `reserved_qty` | Stock committed to outbound demand but not shipped |
| `incoming_qty` | Expected inbound quantity not yet received |
| `in_transit_qty` | Stock dispatched from one warehouse but not received by another |
| `available_qty` | Derived: `physical_qty - reserved_qty` |

For the current schema:

- `inventory.quantity` becomes total `physical_qty` or is replaced by a materialized summary.
- `warehouse_inventory.quantity` becomes `physical_qty`.
- Add `reserved_qty`, `incoming_qty`, and `in_transit_qty` to warehouse-level rows.
- Add a persistent reservation table so ATP is enforceable.

Recommended new/changed tables:

```text
stock_balances
  id
  product_id
  warehouse_id
  location_id nullable
  lot_id nullable
  physical_qty
  reserved_qty
  incoming_qty
  in_transit_qty
  updated_at

stock_reservations
  reservation_id
  source_type
  source_id
  document_id nullable
  product_id
  warehouse_id
  requested_qty
  reserved_qty
  released_qty
  consumed_qty
  status
  expires_at nullable
  created_by
  created_at
  updated_at

inventory_transactions
  transaction_id
  transaction_type
  reason_code nullable
  document_id nullable
  document_line_id nullable
  product_id
  from_warehouse_id nullable
  to_warehouse_id nullable
  quantity
  quantity_sign
  reservation_id nullable
  source_event_id nullable
  idempotency_key
  performed_by
  performed_at
  payload_json
```

Keep `inventory_movement_ledger` only if it becomes the compatibility name for
`inventory_transactions`; otherwise migrate it into the new ledger.

## 5. Document Model Refactor

Current documents should become operational requests, not the stock ledger itself.

### 5.1 Header Fields

Add:

- `transaction_type`
- `reason_code`
- `business_partner_type` (`supplier`, `customer`, `internal`, `production`, nullable)
- `business_partner_id`
- `reference_type`
- `reference_id`
- `requested_by`
- `approved_by`
- `assigned_to`
- `executed_by`
- `requested_at`
- `approved_at`
- `execution_started_at`
- `completed_at`
- `cancelled_at`

Keep existing fields during migration:

- `doc_type`
- `from_warehouse_id`
- `to_warehouse_id`
- `customer_id`
- `created_by`
- `note`

Map old `doc_type` to new `transaction_type`:

| Old doc type | Default transaction type |
| --- | --- |
| `IMPORT` | `PURCHASE_RECEIPT` or `ADJUSTMENT_IN` when no supplier/PO exists |
| `EXPORT` | `ADJUSTMENT_OUT` or `INTERNAL_CONSUMPTION` unless tied to sales/production |
| `SALE` | `SALES_SHIPMENT` |
| `TRANSFER` | `TRANSFER_ISSUE` plus `TRANSFER_RECEIPT` workflow |

### 5.2 Line Fields

Add:

- `requested_qty`
- `reserved_qty`
- `executed_qty`
- `rejected_qty`
- `difference_qty`
- `execution_status`
- `lot_id` nullable
- `location_id` nullable
- `scanned_barcode` nullable
- `qc_status` nullable

Do not overwrite requested quantity when warehouse execution differs. The difference is business
evidence.

## 6. Backend Refactor Plan

### 6.1 Domain Layer

Files to refactor:

- `Services/documents-service/src/app/modules/documents/domain/entities/document.py`
- `Services/inventory-service/src/app/modules/inventory/domain/entities/inventory.py`
- `Services/inventory-service/src/app/modules/inventory/domain/value_objects.py`

Add domain objects:

- `TransactionType`
- `ReasonCode`
- `DocumentStatus` expanded lifecycle
- `ReservationStatus`
- `ExecutionStatus`
- `StockBalance`
- `StockReservation`
- `InventoryTransaction`

Rules:

- inbound transactions do not reserve stock;
- outbound transactions require ATP check before reserve/execute;
- transfer issue creates in-transit stock;
- transfer receipt consumes in-transit stock;
- physical stock changes only from execution confirmation or reversal;
- completed transactions are immutable;
- reversal creates a new ledger entry.

### 6.2 Application Services

Current:

- `DocumentService.create_*_document()`
- `DocumentService.post_document()`
- `InventoryService.reserve_stock()`
- `InventoryService.apply_document_movement()`

Target use cases:

- `create_request`
- `submit_request`
- `approve_request`
- `reserve_request_stock`
- `release_request_reservation`
- `start_execution`
- `confirm_execution`
- `complete_request`
- `cancel_request`
- `reverse_transaction`
- `adjust_stock`
- `count_stock`
- `list_availability`
- `list_inventory_transactions`

Important behavior changes:

- `approve_request` validates business approval only; it does not move stock.
- `reserve_request_stock` persists reservations and reduces available quantity.
- `confirm_execution` writes `inventory_transactions` and updates stock balances.
- `complete_request` requires all required lines to be executed or explicitly short-closed.
- `post_document` should become a deprecated compatibility wrapper:
  - inbound: approve + confirm requested quantities;
  - outbound: approve + reserve + confirm requested quantities;
  - transfer: approve + issue only, or reject compatibility if two-step transfer is required.

### 6.3 Repository/DB Layer

Files to refactor:

- `Services/documents-service/src/app/modules/documents/infrastructure/models/document.py`
- `Services/documents-service/src/app/modules/documents/infrastructure/models/document_item.py`
- `Services/documents-service/src/app/modules/documents/infrastructure/repositories/document_repo.py`
- `Services/inventory-service/src/app/modules/inventory/infrastructure/models/inventory.py`
- `Services/inventory-service/src/app/modules/inventory/infrastructure/models/warehouse_inventory.py`
- `Services/inventory-service/src/app/modules/inventory/infrastructure/models/movement_ledger.py`
- `Services/inventory-service/src/app/modules/inventory/infrastructure/repositories/inventory_repo.py`

Add:

- model for `stock_reservations`;
- model for `inventory_transactions`;
- balance update methods that lock rows during reserve/execute;
- unique idempotency key constraints;
- indexes for `document_id`, `transaction_type`, `product_id`, `warehouse_id`, `status`.

In hybrid core DB mode, these tables should live in the shared core DB and be migrated through
`core-migrate`.

### 6.4 Eventing

Current important events:

- `DocumentUploaded`
- `DocumentPosted`
- `InventoryMovementRequested`
- `InventoryMovementApplied`
- `StockReserved`
- `ReservationReleased`
- `InventoryAdjusted`

Target events:

- `DocumentRequested`
- `DocumentApproved`
- `StockReserved`
- `ReservationReleased`
- `WarehouseExecutionStarted`
- `InventoryTransactionRecorded`
- `DocumentPartiallyExecuted`
- `DocumentCompleted`
- `DocumentCancelled`
- `InventoryAdjusted`
- `TransferIssued`
- `TransferReceived`

`InventoryMovementRequested` should be deprecated once core consistency no longer depends on
events. Reporting, audit, and AI should consume post-commit facts from outbox/events.

## 7. API And gRPC Contract Plan

Files to refactor:

- `proto/wms/documents/v1/documents.proto`
- `proto/wms/inventory/v1/inventory.proto`
- generated `*_pb2.py` after proto changes;
- `Services/documents-service/src/documents_service/grpc_servicer.py`
- `Services/inventory-service/src/inventory_service/grpc_servicer.py`
- `Services/api-gateway/src/api_gateway/routes.py`
- `Services/api-gateway/src/api_gateway/schemas.py`
- `Services/api-gateway/src/api_gateway/presenters.py`

### 7.1 Documents gRPC

Add RPCs:

- `CreateRequest`
- `ApproveRequest`
- `ReserveRequestStock`
- `ReleaseReservation`
- `StartExecution`
- `ConfirmExecution`
- `CompleteRequest`
- `CancelRequest`
- `ReverseDocumentTransaction`
- `ListDocumentLines`

Keep old RPCs temporarily:

- `CreateImport`
- `CreateExport`
- `CreateSale`
- `CreateTransfer`
- `PostDocument`

Mark old RPCs as compatibility endpoints and migrate dashboard away from them.

### 7.2 Inventory gRPC

Add RPCs:

- `GetAvailability`
- `ListStockBalances`
- `ListReservations`
- `ReserveStock`
- `ReleaseReservation`
- `ConfirmInventoryTransaction`
- `ListInventoryTransactions`

Update inventory response shapes to include:

- `physical_qty`
- `reserved_qty`
- `incoming_qty`
- `in_transit_qty`
- `available_qty`

### 7.3 REST Gateway

Add REST endpoints:

```text
POST /api/v1/documents/requests
POST /api/v1/documents/{id}/approve
POST /api/v1/documents/{id}/reserve
POST /api/v1/documents/{id}/release-reservation
POST /api/v1/documents/{id}/start-execution
POST /api/v1/documents/{id}/confirm
POST /api/v1/documents/{id}/complete
POST /api/v1/documents/{id}/cancel
POST /api/v1/documents/{id}/reverse

GET  /api/v1/inventory/availability
GET  /api/v1/inventory/balances
GET  /api/v1/inventory/reservations
GET  /api/v1/inventory/transactions
POST /api/v1/inventory/adjustments
```

Keep existing endpoints during migration:

- `POST /api/v1/documents/import`
- `POST /api/v1/documents/export`
- `POST /api/v1/documents/sale`
- `POST /api/v1/documents/transfer`
- `POST /api/v1/documents/{id}/post`

## 8. Frontend/Dashboard Plan

Files to refactor:

- `dashboard/index.html`
- `dashboard/script.js`
- `dashboard/styles.css`
- `dashboard/tests/e2e.spec.ts`

### 8.1 Navigation And Screens

Split current `Documents` screen into clearer operations:

- `Requests`: create and approve operational requests.
- `Warehouse Execution`: receive/pick/ship/transfer/adjust actual quantities.
- `Reservations`: show blocked stock and release/expire reservations.
- `Inventory Ledger`: immutable stock movement history.
- Keep `Inventory` but show quantity matrix.

### 8.2 Create Request Form

Replace generic document type select with transaction type groups:

- Inbound: purchase receipt, production receipt, sales return, transfer receipt, adjustment in.
- Outbound: sales shipment, production issue, purchase return, transfer issue, consumption, scrap,
  adjustment out.

Fields should change by transaction type:

- sale shipment requires customer and source warehouse;
- purchase receipt should allow supplier/reference;
- transfer requires source and destination warehouse;
- adjustment requires reason code;
- production issue/receipt should allow work order reference.

### 8.3 Document List Actions

Replace one `Approve & Post` button with workflow actions by status:

| Status | Actions |
| --- | --- |
| `DRAFT` | Submit, Edit, Delete |
| `REQUESTED` | Approve, Cancel |
| `APPROVED` | Reserve where applicable, Start Execution, Cancel |
| `RESERVED` | Start Picking/Execution, Release Reservation |
| `IN_PROGRESS` | Confirm Actual Qty, Short Close |
| `PARTIALLY_EXECUTED` | Continue Execution, Complete Short, Reverse line if allowed |
| `COMPLETED` | View Ledger, Reverse |
| `CANCELLED` | View only |

### 8.4 Execution UX

Add execution modal:

- requested quantity shown read-only;
- actual quantity input per line;
- location/bin input;
- barcode/lot fields optional;
- difference reason required when actual quantity differs;
- validation warns when outbound actual quantity exceeds available quantity;
- transfer flow shows issue and receipt separately.

### 8.5 Inventory UI

Update inventory table:

- Product
- Warehouse
- Physical
- Reserved
- Incoming
- In Transit
- Available
- Actions

Add drilldowns:

- reservations for product/warehouse;
- ledger movements;
- documents causing reserved stock.

## 9. Reporting, Audit, AI

### Reporting

Update projections to understand:

- reservation events;
- actual execution quantity vs requested quantity;
- transaction types and reason codes;
- transfer in-transit quantities;
- adjustment reasons.

Files:

- `Services/reporting-service/src/app/modules/reporting/infrastructure/models/projections.py`
- `Services/reporting-service/src/app/modules/reporting/infrastructure/repositories/read_model_repo.py`

### Audit

Audit should record:

- approval;
- reservation;
- release;
- execution confirmation;
- quantity differences;
- reversals;
- adjustment reason codes.

### AI

AI structured query templates should learn the new terms:

- available quantity;
- reserved stock;
- in-transit;
- transaction type;
- stock ledger;
- pending execution.

## 10. Trackable Refactor Roadmap

Use small additive phases. Each phase should end with a commit and a focused verification set.
Avoid mixing DB shape, business logic, API contracts, and dashboard changes in the same phase unless
the phase explicitly says so.

### Phase 0: Baseline And Safety Net

Goal: capture current behavior before changing it.

Scope:

- Add/refresh tests around current document posting and inventory movement.
- Document current compatibility behavior for:
  - import post increases stock;
  - export/sale post decreases stock;
  - transfer post moves stock;
  - duplicate `InventoryMovementRequested` is idempotent.
- Add failing or skipped tests for the target business gaps:
  - sales reservation should reduce available quantity;
  - approve should not directly change physical stock;
  - confirm execution should use actual quantity.

Do not:

- change database schema;
- change API contracts;
- change dashboard behavior.

Verification:

- existing document/inventory unit tests pass;
- new baseline tests pass;
- target-gap tests are marked as expected failures or documented as pending.

Rollback:

- revert only tests/docs from this phase.

### Phase 1: Shared Vocabulary And Compatibility Mapping

Goal: introduce the new business language without changing runtime behavior.

Scope:

- Add enums/constants for:
  - `TransactionType`;
  - `ReasonCode`;
  - expanded `DocumentStatus`;
  - `ReservationStatus`;
  - `ExecutionStatus`.
- Add mapping from existing `doc_type` to default `transaction_type`.
- Add serializer/presenter fields with safe defaults:
  - `transaction_type`;
  - `reason_code`;
  - `requested_qty`;
  - `executed_qty`;
  - `available_qty`.

Do not:

- enforce new lifecycle yet;
- remove `doc_type`;
- modify stock quantities.

Verification:

- old API responses stay backward compatible;
- new fields appear as default/null values where supported;
- contract tests prove existing clients can ignore the new fields.

Rollback:

- remove additive enum/default fields.

### Phase 2: Additive DB Schema For Quantity Matrix

Goal: add stock-balance fields without changing calculations yet.

Scope:

- Add nullable or defaulted fields to warehouse-level stock:
  - `physical_qty`;
  - `reserved_qty`;
  - `incoming_qty`;
  - `in_transit_qty`.
- Backfill `physical_qty` from existing `warehouse_inventory.quantity`.
- Add compatibility rule:
  - old `quantity` and new `physical_qty` remain equal during this phase.
- Add indexes for product/warehouse balance reads.

Do not:

- change `reserve_stock()`;
- change `apply_document_movement()`;
- change dashboard tables yet.

Verification:

- migration test proves backfill works;
- existing inventory reads still return the old `quantity`;
- consistency test proves `quantity == physical_qty` after existing import/export/transfer flows.

Rollback:

- keep old `quantity` authoritative and ignore new fields.

### Phase 3: Inventory Read API Shows Availability

Goal: expose the quantity matrix as read-only data.

Scope:

- Update inventory repository read methods to calculate:
  - `physical_qty`;
  - `reserved_qty`;
  - `incoming_qty`;
  - `in_transit_qty`;
  - `available_qty = physical_qty - reserved_qty`.
- Add gRPC/REST read fields for availability.
- Keep old `quantity` in responses as an alias for `physical_qty`.
- Update reporting/AI only if they parse inventory response shape directly.

Do not:

- persist reservations;
- change document lifecycle;
- change dashboard actions.

Verification:

- `/api/v1/inventory` and `/api/v1/inventory/by-warehouse` still work;
- new availability fields are present;
- old frontend still renders with `quantity`.

Rollback:

- hide new fields in presenter/API while keeping DB columns.

### Phase 4: Persistent Reservations

Goal: make reservation real and testable before touching documents.

Scope:

- Add `stock_reservations`.
- Implement repository methods:
  - create reservation;
  - consume reservation;
  - release reservation;
  - list reservations;
  - calculate available stock with reservations.
- Make `InventoryService.reserve_stock()` persist reservation rows and update `reserved_qty`.
- Make `release_reservation()` reduce `reserved_qty`.
- Add idempotency keys for reservation/release.

Do not:

- call reservation from document posting yet;
- change dashboard document workflow.

Verification:

- reserving stock leaves `physical_qty` unchanged;
- reserving stock reduces `available_qty`;
- second reservation cannot exceed ATP;
- release restores `available_qty`;
- reservation replay is idempotent.

Rollback:

- disable reservation writes via feature flag or stop calling the new service methods.

### Phase 5: Reservation API And Minimal UI Visibility

Goal: let users and tests inspect reservations.

Scope:

- Add gRPC/REST:
  - `GET /api/v1/inventory/availability`;
  - `GET /api/v1/inventory/reservations`;
  - optional `POST /api/v1/inventory/reservations/{id}/release`.
- Update dashboard inventory table to show:
  - Physical;
  - Reserved;
  - Available.
- Add a simple reservations table or drilldown.

Do not:

- redesign full document screen yet;
- remove `Approve & Post`.

Verification:

- dashboard still loads;
- inventory table shows old and new quantity fields clearly;
- e2e test can create/read/release a reservation through API or UI.

Rollback:

- hide reservation UI while leaving backend available.

### Phase 6: Document Lifecycle Fields

Goal: prepare documents to become operational requests.

Scope:

- Add document header fields:
  - `transaction_type`;
  - `reason_code`;
  - `requested_by`;
  - `approved_at`;
  - `execution_started_at`;
  - `completed_at`;
  - `assigned_to`.
- Add document line fields:
  - `requested_qty`;
  - `reserved_qty`;
  - `executed_qty`;
  - `difference_qty`;
  - `execution_status`.
- Backfill `requested_qty` from existing `quantity`.
- Keep old fields and old statuses working.

Do not:

- enforce the new lifecycle;
- change `/documents/{id}/post`.

Verification:

- old create/list/get document flows still pass;
- new fields round-trip in repository tests;
- `requested_qty == quantity` for old documents.

Rollback:

- ignore new document fields in service/presenter.

### Phase 7: Approve Without Stock Movement

Goal: split approval from stock execution for new endpoints while keeping old `/post`.

Scope:

- Add application use case `approve_request`.
- Add gRPC/REST:
  - `POST /api/v1/documents/{id}/approve`.
- New approve endpoint changes document status/approval metadata only.
- Keep old `/documents/{id}/post` as compatibility behavior.

Do not:

- migrate dashboard to the new endpoint yet;
- remove `DocumentPosted`.

Verification:

- approving through new endpoint does not change `physical_qty`;
- old `/post` still changes stock for legacy tests;
- document cannot be approved twice by different users unless explicitly allowed.

Rollback:

- remove/hide the new approve endpoint.

### Phase 8: Sales Reservation Workflow

Goal: fix double-selling for the highest-risk outbound flow.

Scope:

- Add document-level use case `reserve_request_stock`.
- For `SALE` / `SALES_SHIPMENT`, reserve each line from source warehouse.
- Update document line `reserved_qty`.
- Add gRPC/REST:
  - `POST /api/v1/documents/{id}/reserve`;
  - `POST /api/v1/documents/{id}/release-reservation`.
- Emit `StockReserved` and `ReservationReleased`.

Do not:

- implement transfer in-transit yet;
- implement all transaction types yet.

Verification:

- sales approval + reserve reduces available but not physical;
- second sale cannot reserve already reserved quantity;
- releasing reservation restores available;
- reservation is linked to document and line.

Rollback:

- disable document-reservation call path; reservations can be released safely.

### Phase 9: Inventory Transaction Ledger

Goal: create immutable evidence before using execution confirmation.

Scope:

- Add `inventory_transactions` or evolve `inventory_movement_ledger`.
- Add ledger write method with idempotency.
- Record transaction type, document id, line id, product, warehouse, quantity, user, timestamp,
  and payload.
- Add read API:
  - `GET /api/v1/inventory/transactions`.

Do not:

- change stock mutation to use ledger yet;
- update reporting projections yet.

Verification:

- ledger insert is idempotent;
- ledger list can filter by document/product/warehouse;
- old movement ledger compatibility still passes.

Rollback:

- stop writing new ledger rows and keep existing movement ledger.

### Phase 10: Execution Confirmation For Sales

Goal: make physical stock move from actual warehouse confirmation.

Scope:

- Add use case `confirm_execution`.
- For sales shipments:
  - validate reservation;
  - accept actual quantity per line;
  - reduce `physical_qty`;
  - consume reservation;
  - write ledger transaction;
  - update document line `executed_qty` and `difference_qty`.
- Add gRPC/REST:
  - `POST /api/v1/documents/{id}/start-execution`;
  - `POST /api/v1/documents/{id}/confirm`;
  - `POST /api/v1/documents/{id}/complete`.

Do not:

- change import/export/transfer behavior yet;
- remove old `/post`.

Verification:

- confirming sales shipment reduces physical and reserved quantities;
- partial actual quantity records difference;
- confirmation cannot exceed reservation/available stock;
- duplicate confirmation is idempotent.

Rollback:

- keep sales documents in approved/reserved state and release reservations if needed.

### Phase 11: Dashboard Sales Workflow

Goal: migrate one frontend workflow end-to-end.

Scope:

- For sale documents only, replace `Approve & Post` with:
  - Approve;
  - Reserve;
  - Start Execution;
  - Confirm Actual Qty;
  - Complete.
- Add execution modal for actual quantity.
- Update document list status badges.
- Add e2e for sales reservation + shipment confirmation.

Do not:

- redesign every transaction type form yet;
- remove old button for import/export/transfer compatibility.

Verification:

- user can complete a sale from dashboard;
- double-selling is prevented visibly;
- inventory table updates physical/reserved/available correctly.

Rollback:

- show old sale post button again while keeping backend endpoints.

### Phase 12: Inbound Execution

Goal: stop imports from increasing stock before warehouse confirmation.

Scope:

- Implement execution confirmation for:
  - `PURCHASE_RECEIPT`;
  - `PRODUCTION_RECEIPT`;
  - `SALES_RETURN_RECEIPT`;
  - `ADJUSTMENT_IN`.
- Add reason/reference validation where required.
- Update dashboard inbound forms and execution modal.

Do not:

- implement transfer in-transit in the same phase.

Verification:

- purchase receipt approval does not change physical stock;
- confirm receipt increases physical stock by actual quantity;
- adjustment in requires reason code;
- partial receipt records difference.

Rollback:

- keep legacy import `/post` compatibility path.

### Phase 13: Outbound Non-Sales Execution

Goal: generalize outbound execution after sales is stable.

Scope:

- Implement:
  - `PRODUCTION_ISSUE`;
  - `PURCHASE_RETURN_SHIPMENT`;
  - `INTERNAL_CONSUMPTION`;
  - `SCRAP`;
  - `ADJUSTMENT_OUT`.
- Require reason/reference fields for adjustment, consumption, and scrap.
- Use reservation where the transaction type needs allocation before execution.

Verification:

- outbound physical stock changes only on confirmation;
- adjustment out requires reason code;
- insufficient stock errors are clear.

Rollback:

- route unsupported outbound types back to legacy export compatibility temporarily.

### Phase 14: Transfer Issue And Receipt

Goal: model in-transit stock correctly.

Scope:

- Split transfer into:
  - `TRANSFER_ISSUE`;
  - `TRANSFER_RECEIPT`.
- Issue reduces source physical and increases `in_transit_qty`.
- Receipt reduces `in_transit_qty` and increases destination physical.
- Add dashboard transfer execution/receipt views.

Verification:

- total company stock remains stable during transfer;
- source and destination stock are correct;
- in-transit stock is visible and auditable;
- partial receipt is supported or explicitly rejected.

Rollback:

- keep old transfer post path until transfer issue/receipt passes e2e.

### Phase 15: Events, Reporting, Audit, AI

Goal: move downstream systems to post-commit facts.

Scope:

- Add events:
  - `DocumentApproved`;
  - `StockReserved`;
  - `WarehouseExecutionStarted`;
  - `InventoryTransactionRecorded`;
  - `DocumentCompleted`;
  - `TransferIssued`;
  - `TransferReceived`.
- Update reporting projections.
- Update audit consumer.
- Update AI query templates.
- Keep old events during compatibility window.

Verification:

- audit shows approval/reservation/execution/reversal;
- reporting shows requested vs actual quantity;
- AI can answer availability/reservation/in-transit questions.

Rollback:

- keep old projection consumers active while replaying new events in test streams.

### Phase 16: Legacy Compatibility Cleanup

Goal: remove one-step business assumptions after all flows are migrated.

Scope:

- Remove or hide dashboard `Approve & Post`.
- Deprecate old `/documents/{id}/post`.
- Deprecate `InventoryMovementRequested`.
- Update docs and tests to the new lifecycle.
- Rename UI section from `Documents` to `Operations` or `Warehouse Operations` if desired.

Verification:

- no default UI path directly posts stock without execution confirmation;
- old compatibility endpoints either removed or documented as deprecated;
- full e2e suite passes.

Rollback:

- keep compatibility endpoints until at least one release after UI migration.

## 11. Acceptance Tests

Must pass before considering the refactor complete:

- Creating a sales shipment reserves stock and reduces available quantity, but physical quantity
  stays unchanged.
- A second sales shipment cannot reserve already reserved stock.
- Confirming shipment reduces physical quantity and consumes the reservation.
- Confirming partial shipment records requested vs actual difference.
- Purchase receipt increases physical quantity only after warehouse confirmation.
- Transfer issue moves source physical stock into in-transit.
- Transfer receipt removes in-transit and increases destination physical stock.
- Adjustment in/out requires a reason code.
- Completed movements are immutable; reversal creates a new transaction.
- Dashboard no longer shows `Approve & Post` as the only action.
- Inventory screen shows physical, reserved, incoming, in-transit, and available quantities.
- Reporting and audit show transaction type and actual executed quantity.

## 12. Recommended First Implementation Slice

Start with the highest business value and lowest ambiguity:

1. Add quantity matrix to `warehouse_inventory`.
2. Add `stock_reservations`.
3. Make sales document/request reserve stock at approval or explicit reserve step.
4. Add `available_qty` to inventory APIs and dashboard.
5. Replace dashboard `Approve & Post` for sale with:
   - approve;
   - reserve;
   - confirm shipment actual quantity.
6. Add ledger rows for actual shipment.

This directly fixes double-selling risk while creating the foundation for the full inbound,
outbound, transfer, adjustment, and execution model.
