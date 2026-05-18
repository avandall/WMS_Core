"""Role-based permissions enforced at API Gateway."""

from __future__ import annotations

from enum import Enum
from typing import Dict, Set


class Permission(str, Enum):
    VIEW_CUSTOMERS = "view_customers"
    MANAGE_CUSTOMERS = "manage_customers"
    VIEW_PRODUCTS = "view_products"
    VIEW_INVENTORY = "view_inventory"
    VIEW_REPORTS = "view_reports"
    VIEW_WAREHOUSES = "view_warehouses"
    VIEW_DOCUMENTS = "view_documents"
    MANAGE_PRODUCTS = "manage_products"
    MANAGE_INVENTORY = "manage_inventory"
    MANAGE_WAREHOUSES = "manage_warehouses"
    MANAGE_DOCUMENTS = "manage_documents"
    MANAGE_REPORTS = "manage_reports"
    EDIT_PRICES = "edit_prices"
    DOC_CREATE_IMPORT = "doc_create_import"
    DOC_CREATE_EXPORT = "doc_create_export"
    DOC_CREATE_TRANSFER = "doc_create_transfer"
    DOC_POST = "doc_post"
    MANAGE_USERS = "manage_users"


ROLE_PERMISSIONS: Dict[str, Set[Permission]] = {
    "admin": set(p for p in Permission),
    "user": {
        Permission.VIEW_CUSTOMERS,
        Permission.VIEW_PRODUCTS,
        Permission.VIEW_INVENTORY,
        Permission.VIEW_REPORTS,
    },
    "sales": {
        Permission.VIEW_CUSTOMERS,
        Permission.MANAGE_CUSTOMERS,
        Permission.VIEW_PRODUCTS,
        Permission.VIEW_INVENTORY,
        Permission.VIEW_REPORTS,
        Permission.DOC_CREATE_IMPORT,
    },
    "warehouse_manager": {
        Permission.VIEW_CUSTOMERS,
        Permission.VIEW_PRODUCTS,
        Permission.MANAGE_PRODUCTS,
        Permission.VIEW_WAREHOUSES,
        Permission.MANAGE_WAREHOUSES,
        Permission.VIEW_INVENTORY,
        Permission.MANAGE_INVENTORY,
        Permission.VIEW_DOCUMENTS,
        Permission.MANAGE_DOCUMENTS,
        Permission.VIEW_REPORTS,
    },
    "warehouse": {
        Permission.VIEW_CUSTOMERS,
        Permission.VIEW_PRODUCTS,
        Permission.VIEW_INVENTORY,
        Permission.VIEW_REPORTS,
        Permission.DOC_CREATE_TRANSFER,
        Permission.DOC_POST,
    },
    "accountant": {
        Permission.VIEW_CUSTOMERS,
        Permission.VIEW_PRODUCTS,
        Permission.VIEW_INVENTORY,
        Permission.VIEW_REPORTS,
        Permission.EDIT_PRICES,
    },
}


def role_has_permissions(role: str, required: Set[Permission]) -> bool:
    if role == "admin":
        return True
    allowed = ROLE_PERMISSIONS.get(role, set())
    return required.issubset(allowed)
