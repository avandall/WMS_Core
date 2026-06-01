from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints.positions.positions import router as positions_router
from app.api.v1.endpoints.warehouses.warehouses import router as warehouses_router

router = APIRouter()
router.include_router(warehouses_router, prefix="/warehouses", tags=["warehouses"])
router.include_router(positions_router, tags=["positions"])

__all__ = ["router"]
