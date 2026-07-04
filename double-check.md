1. ### Issue description
`release_request_reservation()` clears `reserved_qty` and saves the document even when inventory reservation release fails (exceptions are swallowed). This can leave inventory reserved while the document reports no reservation and emits `ReservationReleased`.

### Issue Context
Inventory reserved quantities are only decremented when the inventory service successfully processes `ReleaseReservation`.

### Fix Focus Areas
- Services/documents-service/src/app/modules/documents/application/services/document_service.py[374-420]

### Suggested fix
- Do **not** clear `item.reserved_qty` (and do not save/commit the document) for a line unless the inventory release succeeded.
- If any line fails to release, either:
  - fail the whole operation (raise a domain/validation error) so the caller can retry safely, **or**
  - keep per-line success/failure and only persist cleared `reserved_qty` for successful lines, and include failures in the response/event.
- At minimum: replace the broad `except Exception: pass` with explicit error handling + logging, and ensure the published event reflects the actual released reservation ids.

2. ### Issue description
The reporting projection updates only `warehouse_matrix` inside `_update_inventory()`, but report endpoints still read `total_quantity` and `warehouse_quantities`. This breaks reporting correctness for event types that still call `_update_inventory()`.

### Issue Context
- `_project()` still routes `InventoryMovementApplied` and `InventoryAdjusted` into `_update_inventory()`.
- `inventory_report()` and `product_report()` read `total_quantity` and `warehouse_quantities`.

### Fix Focus Areas
- Services/reporting-service/src/app/modules/reporting/infrastructure/repositories/read_model_repo.py[46-60]
- Services/reporting-service/src/app/modules/reporting/infrastructure/repositories/read_model_repo.py[329-351]
- Services/reporting-service/src/app/modules/reporting/infrastructure/repositories/read_model_repo.py[353-387]

### Suggested fix
- Option A (preferred): rewrite `_update_inventory()` to call `_update_matrix(product_id, warehouse_id, physical_delta=delta)` so totals and backward-compatible fields are recalculated in one place.
- Option B: after updating `warehouse_matrix`, also:
  - set `row.warehouse_quantities = {wh: data["physical_qty"] for wh, data in matrix.items()}`
  - set `row.total_quantity = sum(data["physical_qty"] for data in matrix.values())`
- Add/adjust tests or a quick projection replay to confirm `inventory_report()` output changes after an `InventoryMovementApplied` event.