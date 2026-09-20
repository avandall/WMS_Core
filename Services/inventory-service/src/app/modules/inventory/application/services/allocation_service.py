from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from app.shared.core.logging import get_logger
from app.shared.domain.business_exceptions import InsufficientStockError, InvalidQuantityError
from app.modules.inventory.domain.interfaces.inventory_repo import IInventoryRepo

logger = get_logger(__name__)


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
        - Locations with an expiry_date are prioritized over locations without expiry_date (nulls last).
        - Locations with expiry_date are sorted ascending (soonest expiry first).
        - Secondary tie-breakers: position_id, id.
        """
        if quantity <= 0:
            raise InvalidQuantityError("Allocation quantity must be a positive integer")

        # 1. Fetch available inventory locations
        locations = self.inventory_repo.get_inventory_locations(
            warehouse_id=warehouse_id,
            product_id=product_id,
            status=status,
        )

        # 2. Filter locations that have available_qty > 0
        candidate_locations = [loc for loc in locations if loc.get("available_qty", 0) > 0]

        if not candidate_locations:
            raise InsufficientStockError(
                f"No available stock to allocate for product {product_id} in warehouse {warehouse_id}"
            )

        # 3. Sort using FEFO rule
        def fefo_sort_key(loc: Dict[str, Any]) -> tuple:
            expiry_val = loc.get("expiry_date")
            has_expiry = expiry_val is not None
            if has_expiry and isinstance(expiry_val, str):
                try:
                    expiry_dt = datetime.fromisoformat(expiry_val)
                except (ValueError, TypeError):
                    expiry_dt = datetime.max
            elif has_expiry and isinstance(expiry_val, datetime):
                expiry_dt = expiry_val
            else:
                expiry_dt = datetime.max

            return (not has_expiry, expiry_dt, loc.get("position_id", 0), loc.get("id", 0))

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
