from typing import Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session
from app.domain.entities.product import Product
from app.core.transaction import TransactionalRepository
from app.domain.interfaces import IProductRepo
from app.infrastructure.persistence.models import InventoryModel, ProductModel


class ProductRepo(TransactionalRepository, IProductRepo):
    """PostgreSQL-backed repository for managing products."""

    def __init__(self, session: Session):
        super().__init__(session)

    def save(self, product: Product) -> None:
        existing = self.session.get(ProductModel, product.product_id)
        if existing:
            existing.name = product.name
            existing.description = product.description
            existing.price = product.price
        else:
            model = ProductModel(
                product_id=product.product_id,
                name=product.name,
                description=product.description,
                price=product.price,
            )
            self.session.add(model)
        self._commit_if_auto()

    def get(self, product_id: int) -> Optional[Product]:
        model = self.session.get(ProductModel, product_id)
        return self._to_domain(model) if model else None

    def get_all(self) -> Dict[int, Product]:
        rows = self.session.execute(select(ProductModel)).scalars().all()
        return {row.product_id: self._to_domain(row) for row in rows}

    def get_price(self, product_id: int) -> float:
        product = self.get(product_id)
        if product:
            return product.price
        raise KeyError("Product not found")

    def delete(self, product_id: int) -> None:
        model = self.session.get(ProductModel, product_id)
        if not model:
            raise KeyError("Product not found")

        # Remove total inventory row if it exists to maintain consistency
        inventory_row = self.session.get(InventoryModel, product_id)
        if inventory_row:
            self.session.delete(inventory_row)

        self.session.delete(model)
        self._commit_if_auto()

    @staticmethod
    def _to_domain(model: ProductModel) -> Product:
        return Product(
            product_id=model.product_id,
            name=model.name,
            description=model.description,
            price=model.price,
        )
