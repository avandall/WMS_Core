from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    email: str
    password: str = Field(min_length=6)
    role: str = Field(default="user")
    full_name: Optional[str] = None


class UserResponse(BaseModel):
    user_id: int
    email: str
    role: str
    full_name: Optional[str]
    is_active: bool

    @classmethod
    def from_domain(cls, user):
        return cls(
            user_id=user.user_id,
            email=user.email,
            role=user.role,
            full_name=user.full_name,
            is_active=user.is_active,
        )


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class RefreshRequest(BaseModel):
    refresh_token: str
