"""Product-related query definitions."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class GetProductQuery:
    """Query to get a specific product."""
    product_id: int


@dataclass
class GetAllProductsQuery:
    """Query to get all products."""
    pass
