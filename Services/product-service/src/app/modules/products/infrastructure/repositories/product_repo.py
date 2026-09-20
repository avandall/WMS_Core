from typing import Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session
from app.modules.products.domain.entities.product import Product, ProductUOM
from app.shared.core.transaction import TransactionalRepository
from app.modules.products.domain.interfaces.product_repo import IProductRepo
from app.modules.products.infrastructure.models.product import ProductModel
from app.modules.products.infrastructure.models.product_uom import ProductUomModel


class ProductRepo(TransactionalRepository, IProductRepo):
    """PostgreSQL-backed repository for managing products."""

    def __init__(self, session: Session, auto_commit: bool = False):
        super().__init__(session, auto_commit)

    def save(self, product: Product) -> None:
        existing = self.session.get(ProductModel, product.product_id)
        if existing:
            existing.name = product.name
            existing.description = product.description
            existing.price = product.price
            existing.length_cm = product.length_cm
            existing.width_cm = product.width_cm
            existing.height_cm = product.height_cm
            existing.gross_weight_kg = product.gross_weight_kg
            existing.net_weight_kg = product.net_weight_kg
            existing.base_uom = product.base_uom

            existing.uoms.clear()
            for u in product.uoms:
                existing.uoms.append(
                    ProductUomModel(
                        product_id=product.product_id,
                        uom_code=u.uom_code,
                        conversion_factor=u.conversion_factor,
                        to_uom_code=u.to_uom_code,
                    )
                )
        else:
            model = ProductModel(
                product_id=product.product_id,
                name=product.name,
                description=product.description,
                price=product.price,
                length_cm=product.length_cm,
                width_cm=product.width_cm,
                height_cm=product.height_cm,
                gross_weight_kg=product.gross_weight_kg,
                net_weight_kg=product.net_weight_kg,
                base_uom=product.base_uom,
                uoms=[
                    ProductUomModel(
                        product_id=product.product_id,
                        uom_code=u.uom_code,
                        conversion_factor=u.conversion_factor,
                        to_uom_code=u.to_uom_code,
                    )
                    for u in product.uoms
                ],
            )
            self.session.add(model)
        self._commit_if_auto()

    def get(self, product_id: int) -> Optional[Product]:
        model = self.session.get(ProductModel, product_id)
        return self._to_domain(model) if model else None

    def get_all(self) -> Dict[int, Product]:
        rows = self.session.execute(select(ProductModel)).scalars().unique().all()
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

        self.session.delete(model)
        self._commit_if_auto()

    @staticmethod
    def _to_domain(model: ProductModel) -> Product:
        return Product(
            product_id=model.product_id,
            name=model.name,
            description=model.description,
            price=model.price,
            length_cm=model.length_cm or 0.0,
            width_cm=model.width_cm or 0.0,
            height_cm=model.height_cm or 0.0,
            gross_weight_kg=model.gross_weight_kg or 0.0,
            net_weight_kg=model.net_weight_kg or 0.0,
            base_uom=model.base_uom or "EACH",
            uoms=[
                ProductUOM(
                    uom_code=u.uom_code,
                    conversion_factor=u.conversion_factor,
                    to_uom_code=u.to_uom_code,
                )
                for u in (model.uoms or [])
            ],
        )
