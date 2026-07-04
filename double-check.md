1.1. Permissions mapping diverges 🐞 Bug ≡ Correctness

GET /api/v1/users/permissions returns a hardcoded role→permission map that diverges from the
gateway’s enforced ROLE_PERMISSIONS, so clients can be told a role has permissions that will still
be denied by the gateway. E.g., the endpoint grants manage_documents to sales/warehouse, but
ROLE_PERMISSIONS for those roles does not include MANAGE_DOCUMENTS.
Agent Prompt
### Issue description
`GET /api/v1/users/permissions` returns a hardcoded permission model that does not match the gateway’s actual enforcement (`ROLE_PERMISSIONS`), causing client/UI authorization confusion and denied requests despite “allowed” display.

### Issue Context
The gateway already has a canonical permission model in `api_gateway/permissions.py` (`Permission` enum + `ROLE_PERMISSIONS`). The endpoint should be generated from that source of truth (or removed).

### Fix Focus Areas
- Services/api-gateway/src/api_gateway/routes.py[1713-1734]
- Services/api-gateway/src/api_gateway/permissions.py[9-73]

2. 2. Reservation sets execution time 🐞 Bug ≡ Correctness

DocumentService.reserve_request_stock() sets document.execution_started_at during reservation,
which conflicts with start_execution() being the lifecycle transition responsible for setting this
timestamp. This will produce incorrect lifecycle/audit timestamps for documents that reserve before
execution.
Agent Prompt
### Issue description
`reserve_request_stock()` sets `execution_started_at`, but `execution_started_at` is also set when transitioning to `IN_PROGRESS` in `start_execution()`. Reserving stock should not mark execution start.

### Issue Context
`start_execution()` documents its responsibility as setting `execution_started_at` during execution start; reservation is a separate lifecycle phase.

### Fix Focus Areas
- Services/documents-service/src/app/modules/documents/application/services/document_service.py[303-309]
- Services/documents-service/src/app/modules/documents/application/services/document_service.py[374-390]

3. 3. Release sets completed_at 🐞 Bug ≡ Correctness

DocumentService.release_request_reservation() sets document.completed_at when releasing
reservations, even though completion is handled by complete_request() when transitioning to
COMPLETED. This can mark documents as “completed” in audit fields without the document actually
being completed.
Agent Prompt
### Issue description
`release_request_reservation()` sets `completed_at`, but completion timestamp should only be set when the document transitions to `COMPLETED` via `complete_request()`.

### Issue Context
The service already has a dedicated `complete_request()` lifecycle method that sets `completed_at` after validating `EXECUTED` status.

### Fix Focus Areas
- Services/documents-service/src/app/modules/documents/application/services/document_service.py[345-356]
- Services/documents-service/src/app/modules/documents/application/services/document_service.py[486-503]

4. 4. Release ledger qty incorrect 🐞 Bug ≡ Correctness

InventoryService.release_reservation() reads the reservation after calling
inventory_repo.release_reservation(), and when released_qty is omitted (the common “release all”
case), the repo has already decremented reserved_qty, so the ledger/event quantity can be recorded
as 0. This corrupts the immutable transaction ledger and emitted ReservationReleased payload.
Agent Prompt
### Issue description
`InventoryService.release_reservation()` derives `qty` from the reservation *after* the repository mutates it. When `released_qty` is `None` (release-all), `reserved_qty` may already be 0, so the ledger entry and event payload log an incorrect released quantity.

### Issue Context
The gRPC handler maps proto `released_qty==0` to `None` (“release all”), so this path is expected and common.

### Fix Focus Areas
- Services/inventory-service/src/app/modules/inventory/application/services/inventory_service.py[241-291]
- Services/inventory-service/src/inventory_service/grpc_servicer.py[203-210]
- Services/inventory-service/src/app/modules/inventory/infrastructure/repositories/inventory_repo.py[316-33]

5. applyInventoryFilters column mapping is now broken by the new filter columns.

The filter-row data-column values were changed to physical, reserved, available, price, value (7 columns total), but applyInventoryFilters (unchanged, ~line 937) still uses columns = ['product', 'warehouse', 'quantity', 'price', 'value']. Consequences:

Typing into "Filter Physical/Reserved/Available" has no effect (those keys aren't in the columns array).
Typing into "Filter Price" now filters against cells[3] (the "Reserved" column), and "Filter Value" filters against cells[4] (the "Available" column) — wrong columns entirely, since the array's indices no longer line up with the new 7-column table.
🐛 Proposed fix
 function applyInventoryFilters() {
     const table = document.querySelector('`#inventory-list` table');
     if (!table) return;
     const filters = {};
     table.querySelectorAll('.filter-row input').forEach(input => {
         filters[input.dataset.column] = input.value.toLowerCase();
     });
     table.querySelectorAll('tbody tr').forEach(row => {
         const cells = row.querySelectorAll('td');
         let match = true;
-        const columns = ['product', 'warehouse', 'quantity', 'price', 'value'];
+        const columns = ['product', 'warehouse', 'physical', 'reserved', 'available', 'price', 'value'];
         columns.forEach((col, idx) => {
             if (filters[col] && !cells[idx]?.textContent.toLowerCase().includes(filters[col])) {
                 match = false;
             }
         });
         row.style.display = match ? '' : 'none';
     });
 }
🤖 Prompt for AI Agents
Verify each finding against current code. Fix only still-valid issues, skip the
rest with a brief reason, keep changes minimal, and validate.

In `@dashboard/script.js` around lines 996 - 1009, Update applyInventoryFilters so
its column list and cell-index mapping match the new 7-column inventory table.
The current columns array in applyInventoryFilters still assumes product,
warehouse, quantity, price, value, so adjust it to include physical, reserved,
and available and ensure each filter-input data-column in the filter row maps to
the correct table cell. Keep the filtering logic in sync with the table
structure so Filter Physical/Reserved/Available work and Price/Value target the
intended columns.

6. Critical: missing closing brace nests all new workflow functions inside loadDocumentDetails, breaking every lifecycle action.

loadDocumentDetails's try { ... } catch (error) { ... } closes at line 3679, but the function itself is never closed there. approveDocument, reserveDocument, startExecution, openConfirmExecutionModal, submitConfirmExecution, and completeDocument are all declared inside loadDocumentDetails's body (the stray extra } at line 3801 is what finally closes loadDocumentDetails). Function declarations nested this way are not hoisted to global/window scope, so every onclick="approveDocument(...)", onclick="reserveDocument(...)", onclick="startExecution(...)", onclick="openConfirmExecutionModal(...)", onsubmit="submitConfirmExecution(event)", and onclick="completeDocument(...)" handler in the rendered HTML will throw ReferenceError at runtime — the entire document approve/reserve/execute/confirm/complete workflow (the core purpose of this PR) is broken.
🤖 Prompt for AI Agents
Verify each finding against current code. Fix only still-valid issues, skip the
rest with a brief reason, keep changes minimal, and validate.

In `@dashboard/script.js` around lines 3665 - 3801, The workflow helpers are
accidentally nested inside loadDocumentDetails because that function is missing
its closing brace before approveDocument, reserveDocument, startExecution,
openConfirmExecutionModal, submitConfirmExecution, and completeDocument. Move
those function declarations back to top-level scope by closing
loadDocumentDetails immediately after its try/catch block and removing the stray
trailing brace, so the onclick and onsubmit handlers can resolve them on
window/global scope.

7. Delegate refresh to identity-service.
/auth/refresh accepts any valid JWT signed with the shared secret, including access tokens, because it never checks type == "refresh". It also reuses the token’s role claim instead of reloading the user, so role changes can be missed. Forward this flow to identity-service or mirror its refresh validation and user lookup here.

🤖 Prompt for AI Agents
Verify each finding against current code. Fix only still-valid issues, skip the
rest with a brief reason, keep changes minimal, and validate.

In `@Services/api-gateway/src/api_gateway/app.py` around lines 116 - 140, The auth
refresh handling in app.py should not accept any JWT signed with the shared
secret or reuse the embedded role claim. Update the /auth/refresh branch in the
request path handler to either delegate refresh to identity-service or mirror
its validation by checking token type is refresh and reloading the user state
before minting a new token. Keep the change centered around the auth/refresh
route logic and the jwt.decode/new_token creation flow so access tokens cannot
be refreshed and role changes are picked up.

8. 🧩 Analysis chain
🏁 Script executed:

set -euo pipefail

echo "== dependency files =="
git ls-files | rg '(^|/)(pyproject.toml|poetry.lock|requirements\.txt|requirements/.*\.txt|uv.lock|Pipfile.lock)$' || true

echo
echo "== target file =="
sed -n '1,180p' Services/audit-service/src/app/shared/core/settings.py

echo
echo "== version hints =="
rg -n "pydantic-settings|pydantic==" -S Services/audit-service/pyproject.toml Services/audit-service/poetry.lock Services/audit-service/requirements.txt Services/audit-service/uv.lock 2>/dev/null || true
Repository: avandall/WMS_Core

Length of output: 4152

🌐 Web query:

pydantic-settings 2.12.0 NoDecode env settings complex list json.loads before field_validator docs

💡 Result:

In pydantic-settings, complex types such as list, set, dict, and sub-models are automatically treated as complex by default, meaning the library attempts to parse their environment variable values as JSON strings [1][2]. If you have a custom format (e.g., a comma-separated string) and want to use a field_validator to process it, this default JSON parsing will cause an error [3]. To prevent this and ensure your validator runs correctly, you must disable the automatic JSON decoding for that specific field using the NoDecode annotation [1][2]. Example implementation: import os from typing import Annotated from pydantic import field_validator from pydantic_settings import BaseSettings, NoDecode class Settings(BaseSettings): # Use NoDecode to prevent pydantic-settings from calling json.loads numbers: Annotated[list[int], NoDecode] @field_validator('numbers', mode='before') @classmethod def decode_numbers(cls, v: str) -> list[int]: # Custom logic to parse the raw environment string return [int(x) for x in v.split(',')] Alternatively, if you want to disable automatic JSON decoding for all fields in a model, you can set enable_decoding=False in the model_config [1][2]: from pydantic_settings import BaseSettings, SettingsConfigDict class Settings(BaseSettings): model_config = SettingsConfigDict(enable_decoding=False) numbers: list[int] @field_validator('numbers', mode='before') @classmethod def decode_numbers(cls, v: str) -> list[int]: return [int(x) for x in v.split(',')] By using NoDecode or disabling global decoding, you ensure the raw environment variable string is passed directly to your validator instead of triggering a JSONDecodeError [3][4].

Citations:

1: https://pydantic.dev/docs/validation/2.12/concepts/pydantic_settings/
2: https://pydantic.dev/docs/validation/latest/concepts/pydantic_settings/
3: Comma separated string as list[str] pydantic/pydantic-settings#570
4: https://stackoverflow.com/questions/78818197/pydantic-settings-isnt-calling-before-validators-properly
mode="before" won’t catch raw env strings for these list[str] fields in pydantic-settings 2.12.0; complex values are JSON-decoded first, so "*" and comma-separated strings still fail during Settings() construction. Add Annotated[list[str], NoDecode] (or disable decoding in model_config) so parse_string_to_list can handle the raw string.

🤖 Prompt for AI Agents
Verify each finding against current code. Fix only still-valid issues, skip the
rest with a brief reason, keep changes minimal, and validate.

In `@Services/audit-service/src/app/shared/core/settings.py` around lines 75 - 93,
The current `parse_string_to_list` validator on `cors_origins`,
`cors_allow_methods`, and `cors_allow_headers` is too late because
pydantic-settings decodes complex `list[str]` env values before `mode="before"`
runs, so raw strings like "*" or comma-separated values still break `Settings()`
creation. Update the `Settings` model so these fields skip automatic decoding by
using `Annotated[list[str], NoDecode]` or by disabling decoding in
`model_config`, then keep `parse_string_to_list` as the normalization point for
the raw string input.

9. 🧩 Analysis chain
🏁 Script executed:

#!/bin/bash
set -euo pipefail

FILE="Services/documents-service/src/app/modules/documents/application/services/document_service.py"

# Map the file structure first
ast-grep outline "$FILE" --view expanded || true

# Show the relevant section with line numbers
sed -n '140,240p' "$FILE"

# Search for status guards and post/approve methods in related modules
rg -n "def (approve|post|complete|confirm|release|reserve)|DocumentStatus\." Services/documents-service/src/app/modules/documents -g '!**/__pycache__/**'
Repository: avandall/WMS_Core

Length of output: 9778

🏁 Script executed:

#!/bin/bash
set -euo pipefail

# Inspect the domain post() guard and related status transitions.
sed -n '180,230p' Services/documents-service/src/app/modules/documents/domain/entities/document.py

# Find all references to approve_request and the API route that calls it.
rg -n "approve_request\(" Services/documents-service/src/app/modules/documents -g '!**/__pycache__/**'
rg -n "approve|post_document|DocumentApproved|DocumentPosted" Services/documents-service/src/app/modules/documents/presentation Services/documents-service/src/app/modules/documents/infrastructure Services/documents-service/src/app/modules/documents/application -g '!**/__pycache__/**'
Repository: avandall/WMS_Core

Length of output: 7357

🏁 Script executed:

#!/bin/bash
set -euo pipefail

# Find the HTTP/controller entrypoint that calls approve_request.
rg -n "approve_request\(|post_document\(|/approve|DocumentService" Services/documents-service/src -g '!**/__pycache__/**' -g '!**/.venv/**'

# Inspect the service method around the transition.
sed -n '171,222p' Services/documents-service/src/app/modules/documents/application/services/document_service.py
Repository: avandall/WMS_Core

Length of output: 3459

Restrict approve_request to DRAFT documents (Services/documents-service/src/app/modules/documents/application/services/document_service.py:171)
approve_request only blocks CANCELLED and already-POSTED documents, so RESERVED, IN_PROGRESS, EXECUTED, and COMPLETED documents can still be reset to POSTED and emit approval/post events. Add the same DRAFT guard here, or delegate to document.post(approved_by).

🤖 Prompt for AI Agents
Verify each finding against current code. Fix only still-valid issues, skip the
rest with a brief reason, keep changes minimal, and validate.

In
`@Services/documents-service/src/app/modules/documents/application/services/document_service.py`
around lines 183 - 197, approve_request currently allows non-DRAFT documents to
be reset to POSTED, so add a DRAFT-only guard in document_service.py within
DocumentService.approve_request before mutating status, or delegate the
transition to document.post(approved_by) so the existing state rules are
enforced. Keep the existing CANCELLED and already-POSTED handling, but ensure
RESERVED, IN_PROGRESS, EXECUTED, and COMPLETED documents are rejected instead of
emitting approval/post events.

10. Verify each finding against current code. Fix only still-valid issues, skip the
rest with a brief reason, keep changes minimal, and validate.

In
`@Services/documents-service/src/app/modules/documents/application/services/document_service.py`
around lines 279 - 310, In reserve_request_stock() within document_service.py,
committed inventory reservations can be left behind if a later reservation or
the document save fails, because the current failure handling only raises
ValidationError and does not undo prior successful ReserveStock calls. Add
compensating rollback logic in this method by tracking each successful
reservation_id (and the related item) inside the loop, then on any exception or
save failure call the existing release_request_reservation() or equivalent
inventory release path for all previously reserved lines before re-raising. Make
sure the rollback happens around the configured_grpc_channel /
InventoryServiceStub flow and before self.document_repo.save(document) so
partial stock reservations are cleaned up consistently.

11. Verify each finding against current code. Fix only still-valid issues, skip the
rest with a brief reason, keep changes minimal, and validate.

In
`@Services/documents-service/src/app/modules/documents/application/services/document_service.py`
around lines 341 - 352, The reservation release flow in
`release_request_reservation` only updates local `reserved_qty` and emits
`ReservationReleased`; it must also invoke the inventory-service
`ReleaseReservation` RPC so the actual stock reservation is unlocked. Update
`release_request_reservation` to call the inventory client for each affected
item (using the existing reservation identifiers) before clearing local state,
and move the `document.completed_at` update out of this method so it only
happens in the completion path for the document lifecycle.

12. Verify each finding against current code. Fix only still-valid issues, skip the
rest with a brief reason, keep changes minimal, and validate.

In `@Services/identity-service/src/identity_service/grpc_servicer.py` around lines
39 - 47, The SQLAlchemy Session is being created on the gRPC worker thread but
then used inside `_run_async` on the dedicated loop thread via `UserRepo`
methods like `get`, `execute`, `add`, `flush`, and `commit`, which can cause
cross-thread session access issues. Move session creation and all DB interaction
into the coroutine executed on the async loop, or keep the entire
repository/database flow on the worker thread; update the `grpc_servicer.py`
flow around `_run_async` and `get_session()` so the same thread owns the
`Session` for its whole lifetime.

13. Verify each finding against current code. Fix only still-valid issues, skip the
rest with a brief reason, keep changes minimal, and validate.

In
`@Services/inventory-service/src/app/modules/inventory/application/services/inventory_service.py`
around lines 176 - 211, reserve_stock is not retry-safe because it always calls
_record_movement after create_reservation, so a replay can duplicate the
InventoryMovementLedger entry. Update the reserve_stock flow in
inventory_service.py to mirror the existing adjust_inventory/adjust_in_transit
pattern by checking inventory_repo.has_movement_event(event_id) early and
short-circuiting when the event was already processed, returning the existing
reservation id instead of writing again. Keep the idempotent behavior centered
around create_reservation and _record_movement so retries do not reinsert the
legacy movement row.

14. Verify each finding against current code. Fix only still-valid issues, skip the
rest with a brief reason, keep changes minimal, and validate.

In
`@Services/inventory-service/src/app/modules/inventory/application/services/inventory_service.py`
around lines 249 - 277, The reservation data is being fetched too late in
inventory_service.py’s release flow, after inventory_repo.release_reservation
has already zeroed reserved_qty. Move the get_reservation lookup in the release
path of the inventory service so it happens before release_reservation, and use
that pre-release snapshot to populate prod_id, wh_id, doc_id, and qty for both
_record_movement and _write_transaction. Keep the existing release_reservation
call and event/transaction recording, but ensure the quantity comes from the
original reservation state rather than the post-release record.

15. Verify each finding against current code. Fix only still-valid issues, skip the
rest with a brief reason, keep changes minimal, and validate.

In
`@Services/inventory-service/src/app/modules/inventory/infrastructure/repositories/inventory_repo.py`
around lines 253 - 314, create_reservation() has a race between reading
WarehouseInventoryModel, checking ATP, and incrementing reserved_qty, so
concurrent requests can overbook stock; fix this by making the warehouse row
update atomic, either by locking the row with a SELECT ... FOR UPDATE before the
availability check or by using a conditional UPDATE that only succeeds when
physical_qty - reserved_qty is sufficient. Apply the same concurrency-safe
pattern to release_reservation() and consume_reservation() so all reserved_qty
changes are protected from read-modify-write races.

16. Verify each finding against current code. Fix only still-valid issues, skip the
rest with a brief reason, keep changes minimal, and validate.

In
`@Services/inventory-service/src/app/modules/inventory/infrastructure/repositories/inventory_repo.py`
around lines 349 - 381, The consume_reservation logic in InventoryRepository
updates the warehouse stock row but leaves WarehouseInventoryModel.quantity
stale, which keeps warehouse summaries inflated. In consume_reservation(), after
locating warehouse_row and applying the reserved_qty and physical_qty
decrements, also update quantity to reflect the consumed stock so
get_warehouse_summary() and get_warehouse_distribution() stay consistent. Use
the existing symbols consume_reservation and WarehouseInventoryModel to keep the
warehouse totals in sync.

17. Verify each finding against current code. Fix only still-valid issues, skip the
rest with a brief reason, keep changes minimal, and validate.

In `@Services/inventory-service/src/inventory_service/grpc_servicer.py` around
lines 203 - 227, `ReleaseReservation` is swallowing all exceptions and returning
only `success=False`, which hides the real failure. Update `ReleaseReservation`
in `grpc_servicer.py` to handle errors like `ConfirmInventoryTransaction` and
`ReserveStock`: catch the exception, log the error with the reservation details,
and set the gRPC status code and details on `context` before returning the
failure response. Keep the existing success path and ensure the `db.close()`
cleanup remains in `finally`.

18. Verify each finding against current code. Fix only still-valid issues, skip the
rest with a brief reason, keep changes minimal, and validate.

In `@Services/inventory-service/src/inventory_service/grpc_servicer.py` around
lines 246 - 268, ListTransactions is passing repository values that may be None
directly into TransactionRow protobuf scalar fields, which can raise TypeError.
Update the TransactionRow construction in grpc_servicer.ListTransactions to
default nullable int64/string fields like document_id, document_line_id,
physical_qty_before/after, reserved_qty_before/after,
available_qty_before/after, and idempotency_key to safe fallbacks, following the
same pattern used by ListReservations. Also fix payload serialization in the
same block so payload is emitted as valid JSON text rather than str(dict), using
the existing tx payload value handling around TransactionRow.

19. Verify each finding against current code. Fix only still-valid issues, skip the
rest with a brief reason, keep changes minimal, and validate.

In
`@Services/reporting-service/src/app/modules/reporting/infrastructure/models/projections.py`
at line 21, The new NOT NULL projection fields are only added in the ORM model,
so existing deployed rows in inventory_summary/document_summary will still be
missing warehouse_matrix and executed_quantity. Add a migration and backfill
path in the reporting schema setup so existing records get safe default values
before the model starts reading/writing them; use the projection model
definitions and the table bootstrapping flow around the reporting app’s
create_all path to locate the change.

20. Verify each finding against current code. Fix only still-valid issues, skip the
rest with a brief reason, keep changes minimal, and validate.

In
`@Services/reporting-service/src/app/modules/reporting/infrastructure/repositories/read_model_repo.py`
around lines 224 - 231, The legacy inventory totals in the read model are being
projected twice because both the domain event handler and
InventoryTransactionRecorded path update the same backward-compatible fields.
Update read_model_repo so warehouse_quantities and total_quantity are maintained
on only one projection path, and make the other handler skip these legacy fields
while still updating warehouse_matrix. Use the existing projection logic around
the row update in the inventory summary repository to keep the totals
single-sourced.