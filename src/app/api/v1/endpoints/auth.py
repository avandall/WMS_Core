from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
import jwt

from app.api.dependencies import get_user_service
from app.application.dtos.auth import (
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    UserCreate,
    UserResponse,
)
from app.modules.users.application.services.user_service import UserService
from app.shared.core.auth import create_token, decode_token
from app.shared.core.settings import settings

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(payload: UserCreate, service: UserService = Depends(get_user_service)):
    user = service.create_user(
        email=payload.email,
        password=payload.password,
        role=payload.role,
        full_name=payload.full_name,
    )
    return UserResponse.from_domain(user)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, service: UserService = Depends(get_user_service)):
    tokens = service.authenticate(payload.email, payload.password)
    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_type="bearer",
        user=UserResponse.from_domain(tokens["user"]),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshRequest, service: UserService = Depends(get_user_service)):
    try:
        decoded = decode_token(payload.refresh_token)
        if decoded.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
            )
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user = service.get_user(int(decoded.get("sub")))
    access = create_token(
        str(user.user_id),
        settings.access_token_expire_minutes,
        {"role": user.role},
    )
    refresh_token = create_token(
        str(user.user_id),
        settings.refresh_token_expire_minutes,
        {"role": user.role, "type": "refresh"},
    )
    return TokenResponse(
        access_token=access,
        refresh_token=refresh_token,
        token_type="bearer",
        user=UserResponse.from_domain(user),
    )

