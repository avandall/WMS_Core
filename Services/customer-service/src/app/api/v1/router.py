from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints.customers.customers import router as customers_router

router = APIRouter()
router.include_router(customers_router, prefix="/customers", tags=["customers"])

__all__ = ["router"]

