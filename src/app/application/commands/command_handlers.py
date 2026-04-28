"""Product command handlers implementing single responsibility principle."""

from typing import Dict, Optional

from app.shared.core.logging import get_logger
from app.modules.products.domain.entities.product import Product
from app.shared.domain.business_exceptions import (
    EntityAlreadyExistsError,
    EntityNotFoundError,
    ValidationError,
)
from app.shared.domain.inventory_repo import IInventoryRepo
from app.shared.domain.product_repo import IProductRepo
from .product_commands import CreateProductCommand, UpdateProductCommand, DeleteProductCommand

logger = get_logger(__name__)


class ProductCommandHandler:
    """Handles product-related commands following SRP."""

    def __init__(self, product_repo: IProductRepo, inventory_repo: IInventoryRepo):
        self.product_repo = product_repo
        self.inventory_repo = inventory_repo

    def handle_create(self, command: CreateProductCommand) -> Product:
        """Handle product creation command."""
        self._validate_create_command(command)
        
        product_id = self._resolve_product_id(command.product_id)
        self._ensure_product_not_exists(product_id)
        
        product = Product(
            product_id=product_id,
            name=command.name,
            price=command.price or 0.0,
            description=command.description,
        )
        
        self.product_repo.save(product)
        self.inventory_repo.add_quantity(product_id, 0)
        
        logger.info(f"Created product: product_id={product_id} name={command.name}")
        return product

    def handle_update(self, command: UpdateProductCommand) -> Product:
        """Handle product update command."""
        product = self._get_product_or_raise(command.product_id)
        
        if command.name is not None:
            product.update_name(command.name)
        if command.price is not None:
            product.update_price(command.price)
        if command.description is not None:
            product.update_description(command.description)
            
        self.product_repo.save(product)
        return product

    def handle_delete(self, command: DeleteProductCommand) -> None:
        """Handle product deletion command."""
        product = self._get_product_or_raise(command.product_id)
        current_quantity = self.inventory_repo.get_quantity(command.product_id)
        
        if current_quantity > 0:
            raise ValidationError(
                f"Cannot delete product {command.product_id}: still has {current_quantity} items in inventory"
            )
            
        self.product_repo.delete(command.product_id)
        self.inventory_repo.delete(command.product_id)

    def _validate_create_command(self, command: CreateProductCommand) -> None:
        """Validate create command parameters."""
        if command.name is None:
            raise ValidationError("Product name cannot be empty")

    def _resolve_product_id(self, product_id: Optional[int]) -> int:
        """Generate product ID if not provided."""
        if product_id is not None:
            return product_id
            
        all_products = self.product_repo.get_all()
        if all_products:
            return max(all_products.keys()) + 1
        return 1

    def _ensure_product_not_exists(self, product_id: int) -> None:
        """Ensure product doesn't already exist."""
        existing_product = self.product_repo.get(product_id)
        if existing_product:
            raise EntityAlreadyExistsError(f"Product with ID {product_id} already exists")

    def _get_product_or_raise(self, product_id: int) -> Product:
        """Get product or raise not found exception."""
        product = self.product_repo.get(product_id)
        if not product:
            raise EntityNotFoundError(f"Product with ID {product_id} not found")
        return product
