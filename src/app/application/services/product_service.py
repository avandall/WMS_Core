from __future__ import annotations

from typing import Optional

from app.core.logging import get_logger
from app.domain.entities.product import Product
from app.domain.exceptions import (
    EntityAlreadyExistsError,
    EntityNotFoundError,
    ValidationError,
)
from app.domain.interfaces import IInventoryRepo, IProductRepo

logger = get_logger(__name__)


class ProductService:
    """Application service for product orchestration."""

    def __init__(self, product_repo: IProductRepo, inventory_repo: IInventoryRepo):
        self.product_repo = product_repo
        self.inventory_repo = inventory_repo

    def create_product(
        self,
        product_id: Optional[int] = None,
        name: Optional[str] = None,
        price: Optional[float] = None,
        description: Optional[str] = None,
    ) -> Product:
        # Backward-compatible positional support:
        # create_product(name, price, description, product_id)
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

        if name is None:
            raise ValidationError("Product name cannot be empty")
        if price is None:
            price = 0.0

        if product_id is None:
            all_products = self.product_repo.get_all()
            product_id = (max(all_products.keys()) + 1) if all_products else 1

        existing_product = self.product_repo.get(product_id)
        if existing_product:
            raise EntityAlreadyExistsError(f"Product with ID {product_id} already exists")

        product = Product(
            product_id=product_id,
            name=name,
            price=price,
            description=description,
        )
        self.product_repo.save(product)
        self.inventory_repo.add_quantity(product_id, 0)
        logger.info(f"Created product: product_id={product_id} name={name}")
        return product

    def get_product_details(self, product_id: int) -> Product:
        product = self.product_repo.get(product_id)
        if not product:
            raise EntityNotFoundError(f"Product with ID {product_id} not found")
        return product

    def update_product(
        self,
        product_id: int,
        name: Optional[str] = None,
        price: Optional[float] = None,
        description: Optional[str] = None,
    ) -> Product:
        product = self.get_product_details(product_id)
        if name is not None:
            product.update_name(name)
        if price is not None:
            product.update_price(price)
        if description is not None:
            product.update_description(description)
        self.product_repo.save(product)
        return product

    def delete_product(self, product_id: int) -> None:
        self.get_product_details(product_id)
        current_quantity = self.inventory_repo.get_quantity(product_id)
        if current_quantity > 0:
            raise ValidationError(
                f"Cannot delete product {product_id}: still has {current_quantity} items in inventory"
            )
        self.product_repo.delete(product_id)
        self.inventory_repo.delete(product_id)

    def get_product_with_inventory(self, product_id: int) -> dict:
        product = self.get_product_details(product_id)
        quantity = self.inventory_repo.get_quantity(product_id)
        return {"product": product, "current_inventory": quantity}

    def list_products_with_inventory(self) -> list:
        products = []
        all_products = self.product_repo.get_all()
        for product_id, product in all_products.items():
            quantity = self.inventory_repo.get_quantity(product_id)
            products.append({"product": product, "current_inventory": quantity})
        return products

    def get_all_products(self) -> list:
        return list(self.product_repo.get_all().values())

    def import_products(self, rows: list[dict]) -> dict:
        created = 0
        updated = 0
        for row in rows:
            product_id = int(row["product_id"])
            name = row["name"]
            price = float(row.get("price", 0))
            description = row.get("description")
            existing = self.product_repo.get(product_id)
            if existing:
                if name:
                    existing.update_name(name)
                existing.update_price(price)
                existing.update_description(description)
                self.product_repo.save(existing)
                updated += 1
            else:
                self.create_product(product_id, name, price, description)
                created += 1
        return {"created": created, "updated": updated}
