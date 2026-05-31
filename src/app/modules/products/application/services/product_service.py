from __future__ import annotations

import csv
import io
from typing import Dict, List, Optional

from app.shared.core.logging import get_logger
from app.shared.core.cache import cached, invalidate_cache_pattern
from app.shared.core.redis import redis_manager
from app.modules.products.domain.entities.product import Product
from app.shared.domain.business_exceptions import ValidationError
from app.modules.inventory.domain.interfaces.inventory_repo import IInventoryRepo
from app.modules.products.domain.interfaces.product_repo import IProductRepo
from app.modules.products.application.commands import (
    CreateProductCommand,
    DeleteProductCommand,
    ProductCommandHandler,
    UpdateProductCommand,
)
from app.modules.products.application.queries import (
    GetAllProductsQuery,
    GetProductQuery,
    ProductQueryHandler,
)
from app.modules.products.application.validation import ProductValidator

logger = get_logger(__name__)


class ProductService:
    """Application service for product orchestration following SOLID principles."""

    def __init__(self, product_repo: IProductRepo, inventory_repo: IInventoryRepo):
        self._command_handler = ProductCommandHandler(product_repo, inventory_repo)
        self._query_handler = ProductQueryHandler(product_repo)
        self._validator = ProductValidator()

    async def create_product(
        self,
        product_id: Optional[int] = None,
        name: Optional[str] = None,
        price: Optional[float] = None,
        description: Optional[str] = None,
    ) -> Product:
        """Create a product using command pattern for SRP compliance."""
        # Handle backward compatibility for legacy positional arguments
        if isinstance(product_id, str):
            legacy_name = product_id
            legacy_price = name
            legacy_description = price
            legacy_product_id = description
            name = legacy_name
            price = legacy_price if isinstance(legacy_price, (int, float)) else None
            description = (
                legacy_description if isinstance(legacy_description, str) else None
            )
            product_id = legacy_product_id if isinstance(legacy_product_id, int) else None

        command = CreateProductCommand(
            product_id=product_id,
            name=name,
            price=price,
            description=description,
        )
        result = self._command_handler.handle_create(command)
        
        # Invalidate products_all cache (best-effort)
        try:
            await redis_manager.delete("products_all")
        except Exception as e:
            logger.error(f"Failed to invalidate products_all cache: {e}")
        
        return result

    @cached(prefix="product", ttl=3600)  # 1 hour cache
    async def get_product_details(self, product_id: int) -> Product:
        """Get product details using query pattern."""
        query = GetProductQuery(product_id=product_id)
        return self._query_handler.handle_get(query)

    @invalidate_cache_pattern("product")
    @invalidate_cache_pattern("products_all")
    async def update_product(
        self,
        product_id: int,
        name: Optional[str] = None,
        price: Optional[float] = None,
        description: Optional[str] = None,
    ) -> Product:
        """Update product using command pattern."""
        command = UpdateProductCommand(
            product_id=product_id,
            name=name,
            price=price,
            description=description,
        )
        result = self._command_handler.handle_update(command)
        
        # Invalidate specific product cache (best-effort)
        try:
            await redis_manager.delete(f"product:{product_id}")
        except Exception as e:
            logger.error(f"Failed to invalidate product cache: {e}")
        
        return result

    @invalidate_cache_pattern("product")
    @invalidate_cache_pattern("products_all")
    async def delete_product(self, product_id: int) -> None:
        """Delete product using command pattern."""
        command = DeleteProductCommand(product_id=product_id)
        self._command_handler.handle_delete(command)
        # Invalidate specific product cache (best-effort)
        try:
            await redis_manager.delete(f"product:{product_id}")
        except Exception as e:
            logger.error(f"Failed to invalidate product cache: {e}")

    async def get_product_with_inventory(self, product_id: int) -> dict:
        """Get product with inventory information - facade method."""
        product = await self.get_product_details(product_id)
        quantity = self._command_handler.inventory_repo.get_quantity(product_id)
        return {"product": product, "current_inventory": quantity}

    def list_products_with_inventory(self) -> List[dict]:
        """List all products with inventory - facade method."""
        products = []
        all_products = self._query_handler.product_repo.get_all()
        for product_id, product in all_products.items():
            quantity = self._command_handler.inventory_repo.get_quantity(product_id)
            products.append({"product": product, "current_inventory": quantity})
        return products

    @cached(prefix="products_all", ttl=1800)  # 30 minutes cache
    async def get_all_products(self) -> List[Product]:
        """Get all products using query pattern."""
        query = GetAllProductsQuery()
        return self._query_handler.handle_get_all(query)

    async def import_products(self, rows: List[Dict]) -> Dict:
        """Import products with separated validation logic."""
        self._validator.validate_csv_rows(rows)
        
        created = 0
        updated = 0
        
        for row in rows:
            product_id = int(row["product_id"])
            name = row["name"]
            price = float(row.get("price", 0))
            description = row.get("description")
            
            self._validator.validate_import_data(product_id, name, price)
            
            existing = self._query_handler.product_repo.get(product_id)
            if existing:
                command = UpdateProductCommand(
                    product_id=product_id,
                    name=name,
                    price=price,
                    description=description,
                )
                self._command_handler.handle_update(command)
                updated += 1
            else:
                command = CreateProductCommand(
                    product_id=product_id,
                    name=name,
                    price=price,
                    description=description,
                )
                self._command_handler.handle_create(command)
                created += 1
                
        result = {"created": created, "updated": updated}
        
        # Use Redis pipeline for bulk cache invalidation (10-20x faster)
        if created > 0 or updated > 0:
            try:
                pipeline = redis_manager.pipeline()
                # Invalidate products_all cache
                pipeline.delete("products_all")
                # Invalidate individual product caches for updated products
                for row in rows:
                    product_id = int(row["product_id"])
                    pipeline.delete(f"product:{product_id}")
                
                await redis_manager.execute_pipeline(pipeline)
                logger.info(f"Invalidated {1 + len(rows)} cache keys using pipeline")
            except Exception as e:
                logger.error(f"Failed to invalidate caches with pipeline: {e}")
        
        return result

    async def import_products_from_csv(self, content: bytes) -> Dict:
        """Parse CSV content and import products."""
        decoded = content.decode("utf-8")
        reader = csv.DictReader(io.StringIO(decoded))
        required = {"product_id", "name", "price"}
        rows = []
        for row in reader:
            if not required.issubset(row.keys()):
                raise ValidationError("CSV must include product_id,name,price")
            rows.append(row)
        result = await self.import_products(rows)
        return {"summary": result, "count": len(rows)}
