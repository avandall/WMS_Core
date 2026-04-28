from __future__ import annotations

from typing import Any, Dict, List

from app.shared.core.logging import get_logger
from app.modules.inventory.domain.entities.inventory import InventoryItem
from app.shared.domain.business_exceptions import EntityNotFoundError, InsufficientStockError, InvalidQuantityError
from app.shared.domain.inventory_repo import IInventoryRepo
from app.shared.domain.product_repo import IProductRepo
from app.shared.domain.warehouse_repo import IWarehouseRepo

logger = get_logger(__name__)


class InventoryService:
    """Application service for inventory orchestration."""

    def __init__(
        self,
        inventory_repo: IInventoryRepo,
        product_repo: IProductRepo,
        warehouse_repo: IWarehouseRepo,
    ):
        self.inventory_repo = inventory_repo
        self.product_repo = product_repo
        self.warehouse_repo = warehouse_repo

    def add_to_total_inventory(self, product_id: int, quantity: int) -> None:
        if quantity < 0:
            raise InvalidQuantityError("Cannot add negative quantity to inventory")
        product = self.product_repo.get(product_id)
        if not product:
            raise EntityNotFoundError(f"Product {product_id} not found")
        self.inventory_repo.add_quantity(product_id, quantity)

    def remove_from_total_inventory(self, product_id: int, quantity: int) -> None:
        if quantity < 0:
            raise InvalidQuantityError("Cannot remove negative quantity from inventory")
        product = self.product_repo.get(product_id)
        if not product:
            raise EntityNotFoundError(f"Product {product_id} not found")
        current_quantity = self.inventory_repo.get_quantity(product_id)
        if current_quantity < quantity:
            raise InsufficientStockError(
                f"Insufficient inventory: only {current_quantity} items available"
            )
        self.inventory_repo.remove_quantity(product_id, quantity)

    def get_total_quantity(self, product_id: int) -> int:
        product = self.product_repo.get(product_id)
        if not product:
            raise EntityNotFoundError(f"Product {product_id} not found")
        return self.inventory_repo.get_quantity(product_id)

    def get_inventory_status(self, product_id: int) -> Dict[str, Any]:
        product = self.product_repo.get(product_id)
        if not product:
            raise EntityNotFoundError(f"Product {product_id} not found")

        total_quantity = self.inventory_repo.get_quantity(product_id)
        warehouse_distribution = []
        total_warehouses = 0
        total_allocated = 0

        for warehouse_id, warehouse in self.warehouse_repo.get_all().items():
            inventory = self.warehouse_repo.get_warehouse_inventory(warehouse_id)
            for item in inventory:
                if item.product_id == product_id:
                    warehouse_distribution.append(
                        {
                            "warehouse_id": warehouse_id,
                            "warehouse_location": warehouse.location,
                            "quantity": item.quantity,
                        }
                    )
                    total_warehouses += 1
                    total_allocated += item.quantity
                    break

        unallocated_quantity = total_quantity - total_allocated
        return {
            "product": product,
            "total_quantity": total_quantity,
            "allocated_quantity": total_allocated,
            "unallocated_quantity": unallocated_quantity,
            "warehouse_count": total_warehouses,
            "warehouse_distribution": warehouse_distribution,
        }

    def get_all_inventory_with_details(self) -> List[Dict[str, Any]]:
        all_inventory = self.inventory_repo.get_all()
        result = []
        for item in all_inventory:
            product = self.product_repo.get(item.product_id)
            if not product:
                continue
            result.append(self.get_inventory_status(item.product_id))
        return result

    def get_low_stock_products(self, threshold: int = 10) -> List[Dict[str, Any]]:
        if threshold < 0:
            raise InvalidQuantityError("Threshold must be non-negative")
        low_stock_products = []
        for item in self.inventory_repo.get_all():
            product = self.product_repo.get(item.product_id)
            if product and item.quantity <= threshold:
                low_stock_products.append(
                    {
                        "product": product,
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

        warehouse_summary = {}
        for warehouse_id, warehouse in self.warehouse_repo.get_all().items():
            inventory = self.warehouse_repo.get_warehouse_inventory(warehouse_id)
            warehouse_items = sum(item.quantity for item in inventory)
            warehouse_products = len(inventory)
            warehouse_summary[warehouse_id] = {
                "location": warehouse.location,
                "total_items": warehouse_items,
                "unique_products": warehouse_products,
            }

        return {
            "total_products": total_products,
            "total_inventory_items": total_items,
            "warehouse_count": len(warehouse_summary),
            "warehouse_summary": warehouse_summary,
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

        rows: List[Dict[str, Any]] = []
        for warehouse_id, warehouse in self.warehouse_repo.get_all().items():
            for item in warehouse.inventory:
                rows.append(
                    {
                        "product_id": item.product_id,
                        "warehouse_id": warehouse_id,
                        "warehouse_name": warehouse.location,
                        "quantity": item.quantity,
                    }
                )
        rows.sort(key=lambda r: (r["warehouse_id"], r["product_id"]))
        return rows

    def validate_inventory_consistency(self) -> List[str]:
        issues = []
        for item in self.inventory_repo.get_all():
            product = self.product_repo.get(item.product_id)
            if not product:
                issues.append(f"Orphaned inventory: product {item.product_id} not found")
                continue

            total_allocated = 0
            for warehouse_id in self.warehouse_repo.get_all().keys():
                inventory = self.warehouse_repo.get_warehouse_inventory(warehouse_id)
                for wh_item in inventory:
                    if wh_item.product_id == item.product_id:
                        total_allocated += wh_item.quantity
                        break

            if total_allocated > item.quantity:
                issues.append(
                    f"Inconsistency for product {item.product_id}: allocated {total_allocated} > total {item.quantity}"
                )
        return issues
