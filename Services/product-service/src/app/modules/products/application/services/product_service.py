from __future__ import annotations

import csv
import io
from typing import Dict, List, Optional

from app.shared.core.logging import get_logger
from app.modules.products.domain.entities.product import Product
from app.shared.domain.business_exceptions import (
    EntityAlreadyExistsError,
    EntityNotFoundError,
    ValidationError,
)
from app.modules.products.domain.interfaces.product_repo import IProductRepo
from app.modules.products.application.dtos import CreateProduct, UpdateProduct

logger = get_logger(__name__)


class ProductService:
    """Application service for product catalog CRUD."""

    def __init__(self, product_repo: IProductRepo, session=None):
        self.product_repo = product_repo
        self.session = session

    def create_product(
        self,
        product_id: Optional[int] = None,
        name: Optional[str] = None,
        price: Optional[float] = None,
        description: Optional[str] = None,
    ) -> Product:
        command = CreateProduct(
            product_id=product_id,
            name=name,
            price=price,
            description=description,
        )
        resolved_product_id = self._resolve_product_id(command.product_id)
        if self.product_repo.get(resolved_product_id):
            raise EntityAlreadyExistsError(
                f"Product with ID {resolved_product_id} already exists"
            )
        if command.name is None:
            raise ValidationError("Product name cannot be empty")

        product = Product(
            product_id=resolved_product_id,
            name=command.name,
            price=command.price or 0.0,
            description=command.description,
        )
        self.product_repo.save(product)
        self._commit_if_needed()
        logger.info("Created product: product_id=%s name=%s", resolved_product_id, command.name)
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
        command = UpdateProduct(
            product_id=product_id,
            name=name,
            price=price,
            description=description,
        )
        product = self.get_product_details(command.product_id)
        if command.name is not None:
            product.update_name(command.name)
        if command.price is not None:
            product.update_price(command.price)
        if command.description is not None:
            product.update_description(command.description)
        self.product_repo.save(product)
        self._commit_if_needed()
        return product

    def delete_product(self, product_id: int) -> None:
        self.get_product_details(product_id)
        self.product_repo.delete(product_id)
        self._commit_if_needed()

    def get_all_products(self) -> List[Product]:
        return list(self.product_repo.get_all().values())

    def import_products(self, rows: List[Dict]) -> Dict:
        """Import products from parsed CSV rows."""
        required = {"product_id", "name", "price"}
        for row in rows:
            if not required.issubset(row.keys()):
                raise ValidationError("CSV must include product_id,name,price")
        
        created = 0
        updated = 0
        
        for row in rows:
            product_id = int(row["product_id"])
            name = row["name"]
            price = float(row.get("price", 0))
            description = row.get("description")
            
            existing = self.product_repo.get(product_id)
            if existing:
                self.update_product(
                    product_id=product_id,
                    name=name,
                    price=price,
                    description=description,
                )
                updated += 1
            else:
                self.create_product(
                    product_id=product_id,
                    name=name,
                    price=price,
                    description=description,
                )
                created += 1
                
        return {"created": created, "updated": updated}

    def import_products_from_csv(self, content: bytes) -> Dict:
        """Parse CSV content and import products."""
        decoded = content.decode("utf-8")
        reader = csv.DictReader(io.StringIO(decoded))
        required = {"product_id", "name", "price"}
        rows = []
        for row in reader:
            if not required.issubset(row.keys()):
                raise ValidationError("CSV must include product_id,name,price")
            rows.append(row)
        result = self.import_products(rows)
        return {"summary": result, "count": len(rows)}

    def _resolve_product_id(self, product_id: Optional[int]) -> int:
        if product_id is not None:
            return product_id
        all_products = self.product_repo.get_all()
        if all_products:
            return max(all_products.keys()) + 1
        return 1

    def _commit_if_needed(self) -> None:
        if self.session is not None:
            self.session.commit()
