from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints.products.products import router as products_router

router = APIRouter()
router.include_router(products_router, prefix="/products", tags=["products"])

__all__ = ["router"]

