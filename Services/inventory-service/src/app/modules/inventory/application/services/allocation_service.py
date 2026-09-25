from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.modules.inventory.domain.interfaces.inventory_repo import IInventoryRepo
from app.shared.core.logging import get_logger
from app.shared.domain.business_exceptions import (
    InsufficientStockError,
    InvalidQuantityError,
)

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

    def allocate_inventory_fefo(
        self,
        *,
        warehouse_id: int,
        product_id: int,
        quantity: int,
        status: str = "AVAILABLE",
        min_shelf_life_days: int = 30,
        min_remaining_shelf_life_days: Optional[int] = None,
        owner_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        TASK-077 / DOM-04: Allocates requested quantity using FEFO rules with
        Minimum Remaining Shelf Life (MRSL) filtering.
        Defaults min_shelf_life_days to 30 days.
        """
        effective_days = (
            min_remaining_shelf_life_days
            if min_remaining_shelf_life_days is not None
            else min_shelf_life_days
        )
        return self.allocate_fefo(
            warehouse_id=warehouse_id,
            product_id=product_id,
            quantity=quantity,
            status=status,
            min_shelf_life_days=effective_days,
            owner_id=owner_id,
        )

    def allocate_fefo(
        self,
        *,
        warehouse_id: int,
        product_id: int,
        quantity: int,
        status: str = "AVAILABLE",
        min_shelf_life_days: int = 0,
        min_remaining_shelf_life_days: Optional[int] = None,
        owner_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Allocates requested quantity of product_id in warehouse_id using FEFO rules.

        Sorting & Filtering logic:
        - Filters out expired stock or stock violating MRSL (expiry_date < now + min_shelf_life_days)
        - Expiry date ASC (earliest expiring first)
        - Locations with NO expiry date placed AFTER locations WITH expiry date
        - Tie-breaking by FIFO: mfg_date ASC (earliest manufacture date first)
        - Fallback tie-breaker by location id ASC (DB insert order)
        - Supports 3PL multi-tenancy (TASK-082 / CRIT-04): isolates inventory by owner_id
        """
        if quantity <= 0:
            raise InvalidQuantityError("Allocation quantity must be greater than zero")

        effective_min_days = max(
            0,
            int(
                min_remaining_shelf_life_days
                if min_remaining_shelf_life_days is not None
                else min_shelf_life_days
            ),
        )

        # 1. Fetch candidate locations (TASK-042 [EDGE-03]: with_for_update to block concurrent over-allocation)
        try:
            locations = self.inventory_repo.get_inventory_locations(
                warehouse_id=warehouse_id,
                product_id=product_id,
                status=status,
                owner_id=owner_id,
                for_update=True,
            )
        except TypeError:
            locations = self.inventory_repo.get_inventory_locations(
                warehouse_id=warehouse_id,
                product_id=product_id,
                status=status,
                owner_id=owner_id,
            )

        # 2. Filter available_qty > 0 and compliant with MRSL (expiry_date >= now + timedelta(days=effective_min_days))
        now = datetime.now(timezone.utc)
        threshold = now + timedelta(days=effective_min_days)

        def is_shelf_life_insufficient(loc: Dict[str, Any]) -> bool:
            has_expiry, expiry_dt = _parse_datetime(loc.get("expiry_date"))
            return has_expiry and expiry_dt < threshold

        candidate_locations = [
            loc for loc in locations
            if loc.get("available_qty", 0) > 0 and not is_shelf_life_insufficient(loc)
        ]
        if not candidate_locations:
            raise InsufficientStockError(
                f"No available stock to allocate for product {product_id} in warehouse {warehouse_id}"
            )

        # Check ATP availability deducting active reservations (RESERVED and PENDING_ADJUSTMENT) [TASK-064 / CRIT-03 & TASK-077 / DOM-04]
        atp_available = self.check_availability(
            warehouse_id=warehouse_id,
            product_id=product_id,
            min_shelf_life_days=effective_min_days,
            locations=locations,
            owner_id=owner_id,
        )
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
                target_owner = loc.get("owner_id") or owner_id or "DEFAULT_OWNER"
                updated_loc = self.inventory_repo.adjust_location_quantity(
                    warehouse_id=loc["warehouse_id"],
                    position_id=loc["position_id"],
                    product_id=loc["product_id"],
                    quantity_delta=0,
                    allocated_delta=alloc_amount,
                    lpn=loc.get("lpn", ""),
                    status=loc.get("status", "AVAILABLE"),
                    lot_number=loc.get("lot_number", ""),
                    owner_id=target_owner,
                )

                allocations.append({
                    "location_id": updated_loc["id"],
                    "warehouse_id": updated_loc["warehouse_id"],
                    "owner_id": updated_loc.get("owner_id", target_owner),
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

    def check_availability(
        self,
        warehouse_id: int,
        product_id: int,
        min_shelf_life_days: int = 30,
        min_remaining_shelf_life_days: Optional[int] = None,
        locations: Optional[List[Dict[str, Any]]] = None,
        owner_id: Optional[str] = None,
    ) -> int:
        """
        Calculates available-to-promise (ATP) stock for product in warehouse.
        Formula (TASK-072 / CRIT-01 & TASK-077 / DOM-04 & TASK-082 / CRIT-04):
        ATP = max(0, Total Valid Physical - max(Total Allocated Loc, Doc Reservations) - Quarantine Reserved)
        Excludes lots with remaining shelf life < min_shelf_life_days.
        Supports 3PL multi-tenancy: isolates ATP calculation by owner_id.
        """
        if locations is None:
            try:
                locations = self.inventory_repo.get_inventory_locations(
                    warehouse_id=warehouse_id,
                    product_id=product_id,
                    status="AVAILABLE",
                    owner_id=owner_id,
                )
            except Exception:
                locations = []

        now = datetime.now(timezone.utc)
        effective_min_days = max(
            0,
            int(
                min_remaining_shelf_life_days
                if min_remaining_shelf_life_days is not None
                else min_shelf_life_days
            ),
        )
        threshold = now + timedelta(days=effective_min_days)

        def is_shelf_life_insufficient(loc: Dict[str, Any]) -> bool:
            has_expiry, expiry_dt = _parse_datetime(loc.get("expiry_date"))
            return has_expiry and expiry_dt < threshold

        valid_locations = [loc for loc in locations if not is_shelf_life_insufficient(loc)]
        has_locations = len(valid_locations) > 0

        doc_reserved = 0
        quarantine_reserved = 0
        session = getattr(self.inventory_repo, "session", None)
        if session is not None:
            from app.modules.inventory.infrastructure.models.stock_reservation import (
                StockReservationModel,
            )
            from app.modules.inventory.infrastructure.models.warehouse_inventory import (
                WarehouseInventoryModel,
            )
            from sqlalchemy import func, select

            doc_query = select(func.coalesce(func.sum(StockReservationModel.reserved_qty), 0)).where(
                StockReservationModel.warehouse_id == warehouse_id,
                StockReservationModel.product_id == product_id,
                StockReservationModel.status == "RESERVED",
            )
            if owner_id:
                doc_query = doc_query.where(StockReservationModel.owner_id == owner_id)
            doc_sum = session.execute(doc_query).scalar() or 0
            doc_reserved = int(doc_sum)

            quarantine_query = select(func.coalesce(func.sum(StockReservationModel.reserved_qty), 0)).where(
                StockReservationModel.warehouse_id == warehouse_id,
                StockReservationModel.product_id == product_id,
                StockReservationModel.status == "PENDING_ADJUSTMENT",
            )
            if owner_id:
                quarantine_query = quarantine_query.where(StockReservationModel.owner_id == owner_id)
            quarantine_sum = session.execute(quarantine_query).scalar() or 0
            quarantine_reserved = int(quarantine_sum)

            if has_locations:
                total_physical = sum(
                    int(loc["quantity"]) if "quantity" in loc and loc["quantity"] is not None else int(loc.get("available_qty", 0))
                    for loc in valid_locations
                )
                total_allocated = sum(int(loc.get("allocated_qty", 0)) for loc in valid_locations)
                return max(0, total_physical - max(total_allocated, doc_reserved) - quarantine_reserved)
            else:
                wh_row = session.execute(
                    select(WarehouseInventoryModel).where(
                        WarehouseInventoryModel.warehouse_id == warehouse_id,
                        WarehouseInventoryModel.product_id == product_id,
                    )
                ).scalar_one_or_none()
                if wh_row:
                    return max(0, int(wh_row.physical_qty) - doc_reserved - quarantine_reserved)
                return 0
        else:
            if hasattr(self.inventory_repo, "list_reservations"):
                all_res = self.inventory_repo.list_reservations(product_id=product_id, warehouse_id=warehouse_id)
                doc_reserved = sum(
                    int(r.get("reserved_qty", 0)) for r in all_res
                    if r.get("status") == "RESERVED" and (not owner_id or r.get("owner_id") == owner_id)
                )
                quarantine_reserved = sum(
                    int(r.get("reserved_qty", 0)) for r in all_res
                    if r.get("status") == "PENDING_ADJUSTMENT" and (not owner_id or r.get("owner_id") == owner_id)
                )
            total_physical = sum(
                int(loc["quantity"]) if "quantity" in loc and loc["quantity"] is not None else int(loc.get("available_qty", 0))
                for loc in valid_locations
            )
            total_allocated = sum(int(loc.get("allocated_qty", 0)) for loc in valid_locations)
            return max(0, total_physical - max(total_allocated, doc_reserved) - quarantine_reserved)
