"""Product authorization logic separated from API endpoints."""

from fastapi import HTTPException

from app.shared.core.permissions import Permission, role_has_permissions
from app.application.dtos.product import ProductUpdate


class ProductAuthorizer:
    """Handles product authorization following SRP."""

    @staticmethod
    def can_update_product(user_role: str, product_update: ProductUpdate) -> None:
        """Check if user can update product with given changes."""
        if product_update.price is not None:
            if not role_has_permissions(user_role, {Permission.EDIT_PRICES}):
                raise HTTPException(status_code=403, detail="Insufficient permissions to edit price")
        
        if any(v is not None for v in [product_update.name, product_update.description]):
            if not role_has_permissions(user_role, {Permission.MANAGE_PRODUCTS}):
                raise HTTPException(status_code=403, detail="Insufficient permissions to edit product")

    @staticmethod
    def can_create_product(user_role: str) -> None:
        """Check if user can create products."""
        if not role_has_permissions(user_role, {Permission.MANAGE_PRODUCTS}):
            raise HTTPException(status_code=403, detail="Insufficient permissions to create product")

    @staticmethod
    def can_delete_product(user_role: str) -> None:
        """Check if user can delete products."""
        if not role_has_permissions(user_role, {Permission.MANAGE_PRODUCTS}):
            raise HTTPException(status_code=403, detail="Insufficient permissions to delete product")
