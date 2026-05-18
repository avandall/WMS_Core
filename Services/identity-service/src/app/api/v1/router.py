from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.positions.positions import router as positions_router
from app.api.v1.endpoints.users.users import router as users_router


router = APIRouter()
router.include_router(users_router, prefix="/users", tags=["users"])
router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(positions_router, tags=["positions"])

__all__ = ["router"]
