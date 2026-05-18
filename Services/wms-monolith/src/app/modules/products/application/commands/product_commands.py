"""Product-related command definitions."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class CreateProductCommand:
    """Command to create a new product."""
    product_id: Optional[int] = None
    name: Optional[str] = None
    price: Optional[float] = None
    description: Optional[str] = None


@dataclass
class UpdateProductCommand:
    """Command to update an existing product."""
    product_id: int
    name: Optional[str] = None
    price: Optional[float] = None
    description: Optional[str] = None


@dataclass
class DeleteProductCommand:
    """Command to delete a product."""
    product_id: int
