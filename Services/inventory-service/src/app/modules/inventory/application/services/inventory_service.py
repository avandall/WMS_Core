from __future__ import annotations

from typing import Any, Dict, List

from app.shared.core.logging import get_logger
from app.modules.inventory.domain.entities.inventory import InventoryItem
from app.shared.domain.business_exceptions import InsufficientStockError, InvalidQuantityError
from app.modules.inventory.domain.interfaces.inventory_repo import IInventoryRepo

logger = get_logger(__name__)


class InventoryService:
    """Application service for inventory orchestration."""

    def __init__(
        self,
        inventory_repo: IInventoryRepo,
    ):
        self.inventory_repo = inventory_repo

    def add_to_total_inventory(self, product_id: int, quantity: int) -> None:
        if quantity < 0:
            raise InvalidQuantityError("Cannot add negative quantity to inventory")
        self.inventory_repo.add_quantity(product_id, quantity)

    def remove_from_total_inventory(self, product_id: int, quantity: int) -> None:
        if quantity < 0:
            raise InvalidQuantityError("Cannot remove negative quantity from inventory")
        current_quantity = self.inventory_repo.get_quantity(product_id)
        if current_quantity < quantity:
            raise InsufficientStockError(
                f"Insufficient inventory: only {current_quantity} items available"
            )
        self.inventory_repo.remove_quantity(product_id, quantity)

    def get_total_quantity(self, product_id: int) -> int:
        return self.inventory_repo.get_quantity(product_id)

    def get_inventory_status(self, product_id: int) -> Dict[str, Any]:
        total_quantity = self.inventory_repo.get_quantity(product_id)
        warehouse_distribution = self.inventory_repo.get_warehouse_distribution(product_id)
        total_allocated = sum(row["quantity"] for row in warehouse_distribution)

        unallocated_quantity = total_quantity - total_allocated
        return {
            "product_id": product_id,
            "total_quantity": total_quantity,
            "allocated_quantity": total_allocated,
            "unallocated_quantity": unallocated_quantity,
            "warehouse_count": len(warehouse_distribution),
            "warehouse_distribution": warehouse_distribution,
        }

    def get_all_inventory_with_details(self) -> List[Dict[str, Any]]:
        all_inventory = self.inventory_repo.get_all()
        result = []
        for item in all_inventory:
            result.append(self.get_inventory_status(item.product_id))
        return result

    def get_low_stock_products(self, threshold: int = 10) -> List[Dict[str, Any]]:
        if threshold < 0:
            raise InvalidQuantityError("Threshold must be non-negative")
        low_stock_products = []
        for item in self.inventory_repo.get_all():
            if item.quantity <= threshold:
                low_stock_products.append(
                    {
                        "product_id": item.product_id,
                        "current_quantity": item.quantity,
                        "threshold": threshold,
                        "needs_restock": True,
                    }
                )
        return low_stock_products

    def get_all_inventory_items(self) -> List[InventoryItem]:
        return self.inventory_repo.get_all()

    def get_inventory_summary(self) -> Dict[str, Any]:
        all_inventory = self.inventory_repo.get_all()
        total_products = len(all_inventory)
        total_items = sum(item.quantity for item in all_inventory)

        return {
            "total_products": total_products,
            "total_inventory_items": total_items,
            "warehouse_summary": self.inventory_repo.get_warehouse_summary(),
            "low_stock_products": self.get_low_stock_products(),
        }

    def get_inventory_by_warehouse_rows(self) -> List[Dict[str, Any]]:
        """Return a flattened list of per-warehouse inventory rows.

        Shape is API-friendly and mirrors the legacy SQL join:
        - product_id
        - warehouse_id
        - warehouse_name (location)
        - quantity
        """

        rows = self.inventory_repo.get_inventory_by_warehouse_rows()
        rows.sort(key=lambda r: (r["warehouse_id"], r["product_id"]))
        return rows

    def validate_inventory_consistency(self) -> List[str]:
        issues = []
        for item in self.inventory_repo.get_all():
            total_allocated = sum(
                row["quantity"]
                for row in self.inventory_repo.get_warehouse_distribution(item.product_id)
            )
            if total_allocated > item.quantity:
                issues.append(
                    f"Inconsistency for product {item.product_id}: allocated {total_allocated} > total {item.quantity}"
                )
        return issues
