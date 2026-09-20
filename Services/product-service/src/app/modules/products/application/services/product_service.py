from __future__ import annotations

import csv
import io
from typing import Any, Dict, List, Optional

from app.modules.products.application.dtos import CreateProduct, UpdateProduct
from app.modules.products.domain.entities.product import Product, ProductUOM
from app.modules.products.domain.interfaces.product_repo import IProductRepo
from app.shared.core.logging import get_logger
from app.shared.domain.business_exceptions import (
    EntityAlreadyExistsError,
    EntityNotFoundError,
    ValidationError,
)

logger = get_logger(__name__)


class ProductService:
    """Application service for product catalog CRUD with physical dimensions & multi-UOM support."""

    def __init__(
        self,
        product_repo: IProductRepo,
        inventory_repo: Optional[Any] = None,
        session: Optional[Any] = None,
    ):
        self.product_repo = product_repo
        self.inventory_repo = inventory_repo
        self.session = session

    async def create_product(
        self,
        *args,
        product_id: Optional[int] = None,
        name: Optional[str] = None,
        price: Optional[float] = None,
        description: Optional[str] = None,
        length_cm: float = 0.0,
        width_cm: float = 0.0,
        height_cm: float = 0.0,
        gross_weight_kg: float = 0.0,
        net_weight_kg: float = 0.0,
        base_uom: str = "EACH",
        uoms: Optional[List[ProductUOM]] = None,
        **kwargs,
    ) -> Product:
        # Legacy positional support: (name, price, description, product_id)
        if args:
            if len(args) >= 1 and name is None:
                name = args[0]
            if len(args) >= 2 and price is None:
                price = args[1]
            if len(args) >= 3 and description is None:
                description = args[2]
            if len(args) >= 4 and product_id is None:
                product_id = args[3]

        command = CreateProduct(
            product_id=product_id,
            name=name,
            price=price,
            description=description,
            length_cm=length_cm,
            width_cm=width_cm,
            height_cm=height_cm,
            gross_weight_kg=gross_weight_kg,
            net_weight_kg=net_weight_kg,
            base_uom=base_uom,
            uoms=uoms,
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
            length_cm=command.length_cm or 0.0,
            width_cm=command.width_cm or 0.0,
            height_cm=command.height_cm or 0.0,
            gross_weight_kg=command.gross_weight_kg or 0.0,
            net_weight_kg=command.net_weight_kg or 0.0,
            base_uom=command.base_uom or "EACH",
            uoms=command.uoms or [],
        )

        self.product_repo.save(product)
        self._commit_if_needed()
        logger.info("Created product: product_id=%s name=%s", resolved_product_id, command.name)
        return product

    async def get_product_details(self, product_id: int) -> Product:
        product = self.product_repo.get(product_id)
        if not product:
            raise EntityNotFoundError(f"Product with ID {product_id} not found")
        return product

    async def update_product(
        self,
        product_id: int,
        name: Optional[str] = None,
        price: Optional[float] = None,
        description: Optional[str] = None,
        length_cm: Optional[float] = None,
        width_cm: Optional[float] = None,
        height_cm: Optional[float] = None,
        gross_weight_kg: Optional[float] = None,
        net_weight_kg: Optional[float] = None,
        base_uom: Optional[str] = None,
        uoms: Optional[List[ProductUOM]] = None,
    ) -> Product:
        product = await self.get_product_details(product_id)
        if name is not None:
            product.update_name(name)
        if price is not None:
            product.update_price(price)
        if description is not None:
            product.update_description(description)
        if length_cm is not None or width_cm is not None or height_cm is not None:
            product.update_dimensions(
                length_cm if length_cm is not None else product.length_cm,
                width_cm if width_cm is not None else product.width_cm,
                height_cm if height_cm is not None else product.height_cm,
            )
        if gross_weight_kg is not None or net_weight_kg is not None:
            product.update_weights(
                gross_weight_kg if gross_weight_kg is not None else product.gross_weight_kg,
                net_weight_kg if net_weight_kg is not None else product.net_weight_kg,
            )
        if base_uom is not None:
            product.base_uom = base_uom
        if uoms is not None:
            product.uoms = uoms

        self.product_repo.save(product)
        self._commit_if_needed()
        return product

    async def delete_product(self, product_id: int) -> None:
        await self.get_product_details(product_id)
        self.product_repo.delete(product_id)
        self._commit_if_needed()

    async def get_all_products(self) -> List[Product]:
        return list(self.product_repo.get_all().values())

    async def get_product_with_inventory(self, product_id: int) -> Dict[str, Any]:
        product = await self.get_product_details(product_id)
        qty = 0
        if self.inventory_repo and hasattr(self.inventory_repo, "get_quantity"):
            qty = self.inventory_repo.get_quantity(product_id)
        return {"product": product, "current_inventory": qty}

    def list_products_with_inventory(self) -> List[Dict[str, Any]]:
        products = list(self.product_repo.get_all().values())
        result = []
        for product in products:
            qty = 0
            if self.inventory_repo and hasattr(self.inventory_repo, "get_quantity"):
                qty = self.inventory_repo.get_quantity(product.product_id)
            result.append({"product": product, "current_inventory": qty})
        return result

    async def import_products(self, rows: List[Dict]) -> Dict:
        """Import products from parsed CSV rows."""
        self._validate_csv_rows(rows)

        created = 0
        updated = 0

        for row in rows:
            product_id = int(row["product_id"])
            name = row["name"]
            price = float(row.get("price", 0))
            description = row.get("description")
            length_cm = float(row.get("length_cm", 0.0))
            width_cm = float(row.get("width_cm", 0.0))
            height_cm = float(row.get("height_cm", 0.0))
            gross_weight_kg = float(row.get("gross_weight_kg", 0.0))
            net_weight_kg = float(row.get("net_weight_kg", 0.0))
            base_uom = row.get("base_uom", "EACH")

            existing = self.product_repo.get(product_id)
            if existing:
                await self.update_product(
                    product_id=product_id,
                    name=name,
                    price=price,
                    description=description,
                    length_cm=length_cm,
                    width_cm=width_cm,
                    height_cm=height_cm,
                    gross_weight_kg=gross_weight_kg,
                    net_weight_kg=net_weight_kg,
                    base_uom=base_uom,
                )
                updated += 1
            else:
                await self.create_product(
                    product_id=product_id,
                    name=name,
                    price=price,
                    description=description,
                    length_cm=length_cm,
                    width_cm=width_cm,
                    height_cm=height_cm,
                    gross_weight_kg=gross_weight_kg,
                    net_weight_kg=net_weight_kg,
                    base_uom=base_uom,
                )
                created += 1

        return {"created": created, "updated": updated}

    async def import_products_from_csv(self, content: bytes) -> Dict:
        """Parse CSV content and import products."""
        decoded = content.decode("utf-8")
        reader = csv.DictReader(io.StringIO(decoded))
        rows = list(reader)
        self._validate_csv_rows(rows)
        result = await self.import_products(rows)
        return {"summary": result, "count": len(rows)}

    def _validate_csv_rows(self, rows: List[Dict]) -> None:
        required = {"product_id", "name"}
        for row in rows:
            if not required.issubset(row.keys()):
                raise ValidationError("CSV must include product_id and name")

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
