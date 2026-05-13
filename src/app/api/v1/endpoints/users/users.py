from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.auth_deps import get_current_user, require_permissions
from app.api.api_deps import get_user_repo, get_user_service
from app.modules.users.application.dtos.auth import UserCreate, UserResponse
from app.modules.users.application.services.user_service import UserService
from app.shared.core.auth import hash_password
from app.shared.core.permissions import Permission, ROLE_PERMISSIONS
from app.shared.core.permissions_store import clear_user_overrides, set_user_overrides
from app.modules.users.domain.entities.user import User

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def me(user=Depends(get_current_user)):
    return UserResponse.from_domain(user)


@router.get(
    "/",
    response_model=list[UserResponse],
    dependencies=[Depends(require_permissions(Permission.MANAGE_USERS))],
)
async def list_users(service: UserService = Depends(get_user_service)):
    users = await service.list_users()
    return [UserResponse.from_domain(u) for u in users.values()]


@router.post(
    "/",
    response_model=UserResponse,
    status_code=201,
    dependencies=[Depends(require_permissions(Permission.MANAGE_USERS))],
)
async def create_user(payload: UserCreate, service: UserService = Depends(get_user_service)):
    user = await service.create_user(
        email=payload.email,
        password=payload.password,
        role=payload.role,
        full_name=payload.full_name,
    )
    return UserResponse.from_domain(user)


@router.get(
    "/permissions",
    dependencies=[Depends(require_permissions(Permission.MANAGE_USERS))],
)
async def list_permissions():
    return {
        "permissions": [p.value for p in Permission],
        "roles": {role: [p.value for p in perms] for role, perms in ROLE_PERMISSIONS.items()},
    }


class RoleUpdatePayload(BaseModel):
    role: str


@router.patch(
    "/{user_id}/role",
    dependencies=[Depends(require_permissions(Permission.MANAGE_USERS))],
)
async def update_role(user_id: int, payload: RoleUpdatePayload, service: UserService = Depends(get_user_service)):
    user = await service.update_role(user_id, payload.role)
    return UserResponse.from_domain(user)


class PermissionsUpdatePayload(BaseModel):
    permissions: list[str] | None = None
    mode: str = "override"  # "override" to set, "clear" to remove overrides


@router.patch(
    "/{user_id}/permissions",
    dependencies=[Depends(require_permissions(Permission.MANAGE_USERS))],
)
async def update_permissions(user_id: int, payload: PermissionsUpdatePayload):
    if payload.mode == "clear":
        clear_user_overrides(user_id)
    else:
        set_user_overrides(user_id, payload.permissions or [])
    return {"user_id": user_id, "status": "ok"}


class ChangePasswordPayload(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6)


@router.post("/me/change-password")
async def change_my_password(
    payload: ChangePasswordPayload,
    user=Depends(get_current_user),
    service: UserService = Depends(get_user_service),
):
    await service.change_password(user.user_id, payload.old_password, payload.new_password)
    return {"status": "ok", "message": "Password changed successfully"}


class ResetPayload(BaseModel):
    new_password: str = Field(min_length=6)


@router.post(
    "/{user_id}/reset-password",
    dependencies=[Depends(require_permissions(Permission.MANAGE_USERS))],
)
async def reset_user_password(
    user_id: int,
    payload: ResetPayload,
    repo=Depends(get_user_repo),
    service: UserService = Depends(get_user_service),
):
    user = await service.get_user(user_id)
    updated = User(
        user_id=user.user_id,
        email=user.email,
        hashed_password=hash_password(payload.new_password),
        role=user.role,
        full_name=user.full_name,
        is_active=user.is_active,
    )
    repo.save(updated)
    return {"status": "ok", "message": "Password reset successfully"}


@router.delete(
    "/{user_id}",
    dependencies=[Depends(require_permissions(Permission.MANAGE_USERS))],
    status_code=204,
)
async def delete_user(
    user_id: int,
    current_user=Depends(get_current_user),
    service: UserService = Depends(get_user_service),
):
    if current_user.user_id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account",
        )
    await service.delete_user(user_id)
    return {"status": "ok", "message": f"User {user_id} deleted successfully"}
