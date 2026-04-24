"""Product query handlers implementing single responsibility principle."""

from typing import List

from app.domain.entities.product import Product
from app.domain.exceptions import EntityNotFoundError
from app.domain.interfaces import IProductRepo
from .product_queries import GetProductQuery, GetAllProductsQuery


class ProductQueryHandler:
    """Handles product-related queries following SRP."""

    def __init__(self, product_repo: IProductRepo):
        self.product_repo = product_repo

    def handle_get(self, query: GetProductQuery) -> Product:
        """Handle get product query."""
        product = self.product_repo.get(query.product_id)
        if not product:
            raise EntityNotFoundError(f"Product with ID {query.product_id} not found")
        return product

    def handle_get_all(self, query: GetAllProductsQuery) -> List[Product]:
        """Handle get all products query."""
        return list(self.product_repo.get_all().values())
