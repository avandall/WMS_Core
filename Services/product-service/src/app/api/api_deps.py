"""Dependency injection for Product Service endpoints."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.modules.products.application.services.product_service import ProductService
from app.modules.products.infrastructure.repositories.product_repo import ProductRepo
from app.modules.inventory.infrastructure.repositories.inventory_repo import InventoryRepo
from app.shared.core.database import get_session


def get_product_repo(db: Session = Depends(get_session)) -> ProductRepo:
    return ProductRepo(db)


def get_product_service(db: Session = Depends(get_session)) -> ProductService:
    return ProductService(product_repo=ProductRepo(db), inventory_repo=InventoryRepo(db))
