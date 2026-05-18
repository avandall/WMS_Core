from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="User password")
    full_name: Optional[str] = Field(None, max_length=100, description="User full name")
    is_active: bool = Field(True, description="Whether the user is active")


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    user_id: int
    email: str
    full_name: Optional[str]
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime]


class UserLogin(BaseModel):
    email: EmailStr = Field(..., description="User email")
    password: str = Field(..., description="User password")


class UserLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class UserChangePassword(BaseModel):
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, description="New password")


class UserListResponse(BaseModel):
    users: List[UserResponse]
    total: int
    page: int
    page_size: int


class UserSearchRequest(BaseModel):
    email: Optional[str] = None
    is_active: Optional[bool] = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
