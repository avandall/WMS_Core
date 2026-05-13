from __future__ import annotations

from typing import Any, Dict, List

from app.shared.core.logging import get_logger
from app.shared.core.cache import cached, invalidate_cache_pattern
from app.shared.core.redis import redis_manager
from app.shared.core.pubsub import EventPublisher
from app.modules.inventory.domain.entities.inventory import InventoryItem
from app.modules.warehouses.domain.entities.warehouse import Warehouse
from app.shared.domain.business_exceptions import (
    EntityAlreadyExistsError,
    InsufficientStockError,
    InvalidQuantityError,
    ProductNotFoundError,
    ValidationError,
    WarehouseNotFoundError,
)
from app.modules.inventory.domain.interfaces.inventory_repo import IInventoryRepo
from app.modules.products.domain.interfaces.product_repo import IProductRepo
from app.modules.warehouses.domain.interfaces.warehouse_repo import IWarehouseRepo
from app.shared.utils.infrastructure import warehouse_id_generator

logger = get_logger(__name__)


class WarehouseService:
    """Application service for warehouse orchestration."""

    def __init__(
        self,
        warehouse_repo: IWarehouseRepo,
        product_repo: IProductRepo,
        inventory_repo: IInventoryRepo,
        id_generator=None,
    ):
        self.warehouse_repo = warehouse_repo
        self.product_repo = product_repo
        self.inventory_repo = inventory_repo
        self._warehouse_id_generator = id_generator or warehouse_id_generator()

    async def create_warehouse(self, location: str) -> Warehouse:
        warehouse_id = self._warehouse_id_generator()
        warehouse = Warehouse(warehouse_id=warehouse_id, location=location)
        self.warehouse_repo.create_warehouse(warehouse)
        return warehouse

    def create_warehouse_with_id(self, warehouse: Warehouse) -> None:
        existing = self.warehouse_repo.get(warehouse.warehouse_id)
        if existing:
            raise EntityAlreadyExistsError(
                f"Warehouse with ID {warehouse.warehouse_id} already exists"
            )
        self.warehouse_repo.create_warehouse(warehouse)

    @cached(prefix="warehouse", ttl=1800)  # 30 minutes cache
    async def get_warehouse(self, warehouse_id: int) -> Warehouse:
        warehouse = self.warehouse_repo.get(warehouse_id)
        if not warehouse:
            raise WarehouseNotFoundError(f"Warehouse {warehouse_id} not found")
        return warehouse

    async def add_product_to_warehouse(
        self, warehouse_id: int, product_id: int, quantity: int
    ) -> None:
        if quantity <= 0:
            raise InvalidQuantityError("Quantity must be positive")
        await self.get_warehouse(warehouse_id)
        product = self.product_repo.get(product_id)
        if not product:
            raise ProductNotFoundError(f"Product {product_id} not found")
        self.warehouse_repo.add_product_to_warehouse(warehouse_id, product_id, quantity)

    async def remove_product_from_warehouse(
        self, warehouse_id: int, product_id: int, quantity: int
    ) -> None:
        if quantity <= 0:
            raise InvalidQuantityError("Quantity must be positive")
        await self.get_warehouse(warehouse_id)
        product = self.product_repo.get(product_id)
        if not product:
            raise ProductNotFoundError(f"Product {product_id} not found")
        current_quantity = await self._get_warehouse_product_quantity(warehouse_id, product_id)
        if current_quantity < quantity:
            raise InsufficientStockError(
                f"Insufficient stock in warehouse: only {current_quantity} items available"
            )
        self.warehouse_repo.remove_product_from_warehouse(
            warehouse_id, product_id, quantity
        )

    async def get_warehouse_inventory(self, warehouse_id: int) -> List[InventoryItem]:
        await self.get_warehouse(warehouse_id)
        return self.warehouse_repo.get_warehouse_inventory(warehouse_id)

    async def transfer_product(
        self,
        from_warehouse_id: int,
        to_warehouse_id: int,
        product_id: int,
        quantity: int,
    ) -> None:
        if quantity <= 0:
            raise InvalidQuantityError("Transfer quantity must be positive")
        if from_warehouse_id == to_warehouse_id:
            raise ValidationError("Cannot transfer to the same warehouse")
        await self.get_warehouse(from_warehouse_id)
        await self.get_warehouse(to_warehouse_id)
        product = self.product_repo.get(product_id)
        if not product:
            raise ProductNotFoundError(f"Product {product_id} not found")
        source_quantity = await self._get_warehouse_product_quantity(from_warehouse_id, product_id)
        if source_quantity < quantity:
            raise InsufficientStockError(
                f"Source warehouse only has {source_quantity} items"
            )
        self.warehouse_repo.remove_product_from_warehouse(
            from_warehouse_id, product_id, quantity
        )
        self.warehouse_repo.add_product_to_warehouse(
            to_warehouse_id, product_id, quantity
        )

    async def get_all_warehouses_with_inventory_summary(self) -> List[Dict[str, Any]]:
        result = []
        for warehouse in self.warehouse_repo.get_all().values():
            inventory = await self.get_warehouse_inventory(warehouse.warehouse_id)
            total_items = sum(item.quantity for item in inventory)
            unique_products = len(inventory)
            result.append(
                {
                    "warehouse": warehouse,
                    "inventory_summary": {
                        "total_items": total_items,
                        "unique_products": unique_products,
                        "inventory_details": inventory,
                    },
                }
            )
        return result

    async def get_all_warehouses(self) -> List[Warehouse]:
        return list(self.warehouse_repo.get_all().values())

    async def transfer_all_inventory(
        self, from_warehouse_id: int, to_warehouse_id: int
    ) -> List[InventoryItem]:
        if from_warehouse_id == to_warehouse_id:
            raise ValidationError("Cannot transfer to the same warehouse")
        await self.get_warehouse(from_warehouse_id)
        await self.get_warehouse(to_warehouse_id)
        source_inventory = self.warehouse_repo.get_warehouse_inventory(from_warehouse_id)
        if not source_inventory:
            return []
        transferred_items = []
        for item in source_inventory:
            self.warehouse_repo.remove_product_from_warehouse(
                from_warehouse_id, item.product_id, item.quantity
            )
            self.warehouse_repo.add_product_to_warehouse(
                to_warehouse_id, item.product_id, item.quantity
            )
            transferred_items.append(item)
        return transferred_items

    async def delete_warehouse(self, warehouse_id: int) -> None:
        await self.get_warehouse(warehouse_id)
        inventory = self.warehouse_repo.get_warehouse_inventory(warehouse_id)
        if inventory:
            total_items = sum(item.quantity for item in inventory)
            unique_products = len(inventory)
            raise ValidationError(
                f"Cannot delete warehouse {warehouse_id}: warehouse still has {total_items} items "
                f"({unique_products} unique products) in stock. "
                f"Use the transfer endpoint to move inventory to another warehouse first."
            )
        self.warehouse_repo.delete(warehouse_id)
        # Invalidate specific warehouse cache (best-effort)
        try:
            await redis_manager.delete(f"warehouse:{warehouse_id}")
        except Exception as e:
            logger.error(f"Failed to invalidate warehouse cache: {e}")

    async def _get_warehouse_product_quantity(self, warehouse_id: int, product_id: int) -> int:
        inventory = self.warehouse_repo.get_warehouse_inventory(warehouse_id)
        for item in inventory:
            if item.product_id == product_id:
                return item.quantity
        return 0
