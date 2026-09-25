from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from app.shared.core.logging import get_logger
from app.shared.domain.business_exceptions import InsufficientStockError, InvalidQuantityError
from app.modules.inventory.domain.interfaces.inventory_repo import IInventoryRepo

logger = get_logger(__name__)


def _parse_datetime(val: Any) -> tuple[bool, datetime]:
    if val is None:
        return False, datetime.max.replace(tzinfo=timezone.utc)
    if isinstance(val, datetime):
        dt = val
    elif isinstance(val, str):
        try:
            dt = datetime.fromisoformat(val)
        except (ValueError, TypeError):
            return False, datetime.max.replace(tzinfo=timezone.utc)
    else:
        return False, datetime.max.replace(tzinfo=timezone.utc)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return True, dt


class AllocationService:
    """Service for FEFO (First-Expired, First-Out) stock allocation and product recall queries."""

    def __init__(self, inventory_repo: IInventoryRepo):
        self.inventory_repo = inventory_repo

    def allocate_fefo(
        self,
        *,
        warehouse_id: int,
        product_id: int,
        quantity: int,
        status: str = "AVAILABLE",
    ) -> List[Dict[str, Any]]:
        """
        Allocates requested quantity of product_id in warehouse_id using FEFO rules.

        Sorting logic:
        - Filters out expired stock (expiry_date < current UTC time)
        - Expiry date ASC (earliest expiring first)
        - Locations with NO expiry date placed AFTER locations WITH expiry date
        - Tie-breaking by FIFO: mfg_date ASC (earliest manufacture date first)
        - Fallback tie-breaker by location id ASC (DB insert order)
        """
        if quantity <= 0:
            raise InvalidQuantityError("Allocation quantity must be greater than zero")

        # 1. Fetch candidate locations (TASK-042 [EDGE-03]: with_for_update to block concurrent over-allocation)
        try:
            locations = self.inventory_repo.get_inventory_locations(
                warehouse_id=warehouse_id,
                product_id=product_id,
                status=status,
                for_update=True,
            )
        except TypeError:
            locations = self.inventory_repo.get_inventory_locations(
                warehouse_id=warehouse_id,
                product_id=product_id,
                status=status,
            )

        # 2. Filter available_qty > 0 and not expired (expiry_date < now)
        now = datetime.now(timezone.utc)

        def is_expired(loc: Dict[str, Any]) -> bool:
            has_expiry, expiry_dt = _parse_datetime(loc.get("expiry_date"))
            return has_expiry and expiry_dt < now

        candidate_locations = [
            loc for loc in locations
            if loc.get("available_qty", 0) > 0 and not is_expired(loc)
        ]
        if not candidate_locations:
            raise InsufficientStockError(
                f"No available stock to allocate for product {product_id} in warehouse {warehouse_id}"
            )

        # Check ATP availability deducting active reservations (RESERVED and PENDING_ADJUSTMENT) [TASK-064 / CRIT-03]
        atp_available = self.check_availability(warehouse_id=warehouse_id, product_id=product_id)
        if quantity > atp_available:
            raise InsufficientStockError(
                f"Insufficient stock for FEFO allocation. ATP Available: {atp_available}, Requested: {quantity}"
            )

        # 3. Sort using FEFO rule with mfg_date FIFO tiebreak
        def fefo_sort_key(loc: Dict[str, Any]) -> tuple:
            has_expiry, expiry_dt = _parse_datetime(loc.get("expiry_date"))
            has_mfg, mfg_dt = _parse_datetime(loc.get("mfg_date"))
            return (not has_expiry, expiry_dt, not has_mfg, mfg_dt, loc.get("id", 0))

        candidate_locations.sort(key=fefo_sort_key)

        # 4. Perform allocation
        allocations: List[Dict[str, Any]] = []
        remaining_qty = quantity

        for loc in candidate_locations:
            avail = loc["available_qty"]
            alloc_amount = min(remaining_qty, avail)

            if alloc_amount > 0:
                updated_loc = self.inventory_repo.adjust_location_quantity(
                    warehouse_id=loc["warehouse_id"],
                    position_id=loc["position_id"],
                    product_id=loc["product_id"],
                    quantity_delta=0,
                    allocated_delta=alloc_amount,
                    lpn=loc.get("lpn", ""),
                    status=loc.get("status", "AVAILABLE"),
                    lot_number=loc.get("lot_number", ""),
                )

                allocations.append({
                    "location_id": updated_loc["id"],
                    "warehouse_id": updated_loc["warehouse_id"],
                    "position_id": updated_loc["position_id"],
                    "product_id": updated_loc["product_id"],
                    "lpn": updated_loc.get("lpn", ""),
                    "lot_number": updated_loc.get("lot_number", ""),
                    "mfg_date": updated_loc.get("mfg_date"),
                    "expiry_date": updated_loc.get("expiry_date"),
                    "allocated_qty": alloc_amount,
                })

                remaining_qty -= alloc_amount

            if remaining_qty == 0:
                break

        if remaining_qty > 0:
            total_allocated = quantity - remaining_qty
            raise InsufficientStockError(
                f"Insufficient stock for FEFO allocation. Requested: {quantity}, Allocated: {total_allocated}, Shortage: {remaining_qty}"
            )

        return allocations

    def recall_query(self, lot_number: str) -> Dict[str, Any]:
        """Query all inventory locations holding the specified lot and all customers/orders receiving it."""
        if not lot_number or not lot_number.strip():
            raise ValueError("lot_number must be a non-empty string")
        return self.inventory_repo.recall_query(lot_number.strip())

    def check_availability(self, warehouse_id: int, product_id: int) -> int:
        """
        Calculates available-to-promise (ATP) stock for product in warehouse.
        Deducts both RESERVED and PENDING_ADJUSTMENT reservations [TASK-064 / CRIT-03].
        """
        try:
            locations = self.inventory_repo.get_inventory_locations(
                warehouse_id=warehouse_id,
                product_id=product_id,
                status="AVAILABLE",
            )
        except Exception:
            locations = []

        now = datetime.now(timezone.utc)

        def is_expired(loc: Dict[str, Any]) -> bool:
            has_expiry, expiry_dt = _parse_datetime(loc.get("expiry_date"))
            return has_expiry and expiry_dt < now

        valid_locations = [loc for loc in locations if not is_expired(loc)]
        has_locations = len(valid_locations) > 0

        active_reserved = 0
        session = getattr(self.inventory_repo, "session", None)
        if session is not None:
            from sqlalchemy import func, select
            from app.modules.inventory.infrastructure.models.stock_reservation import StockReservationModel
            from app.modules.inventory.infrastructure.models.warehouse_inventory import WarehouseInventoryModel

            reserved_sum = session.execute(
                select(func.coalesce(func.sum(StockReservationModel.reserved_qty), 0)).where(
                    StockReservationModel.warehouse_id == warehouse_id,
                    StockReservationModel.product_id == product_id,
                    StockReservationModel.status.in_(["RESERVED", "PENDING_ADJUSTMENT"]),
                )
            ).scalar() or 0
            active_reserved = int(reserved_sum)

            if has_locations:
                loc_avail = sum(int(loc.get("available_qty", 0)) for loc in valid_locations)
                return max(0, loc_avail - active_reserved)
            else:
                wh_row = session.execute(
                    select(WarehouseInventoryModel).where(
                        WarehouseInventoryModel.warehouse_id == warehouse_id,
                        WarehouseInventoryModel.product_id == product_id,
                    )
                ).scalar_one_or_none()
                if wh_row:
                    return max(0, int(wh_row.physical_qty) - active_reserved)
                return 0
        else:
            if hasattr(self.inventory_repo, "list_reservations"):
                all_res = self.inventory_repo.list_reservations(product_id=product_id, warehouse_id=warehouse_id)
                active_reserved = sum(
                    int(r.get("reserved_qty", 0)) for r in all_res
                    if r.get("status") in ("RESERVED", "PENDING_ADJUSTMENT")
                )
            loc_avail = sum(int(loc.get("available_qty", 0)) for loc in valid_locations)
            return max(0, loc_avail - active_reserved)
