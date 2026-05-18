"""Auth dependencies for services (delegates auth to Identity Service)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.shared.core.permissions import Permission, role_has_permissions
from app.shared.core.permissions_store import get_user_overrides


@dataclass(slots=True)
class CurrentUser:
    user_id: int
    role: str
    is_active: bool = True


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    if not creds:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    from customer_service.grpc_identity_client import validate_token

    me = validate_token(creds.credentials, request_id=request.headers.get("x-request-id"))
    if not me:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = CurrentUser(
        user_id=me.user_id,
        role=me.role,
        is_active=me.is_active,
    )
    if not user.user_id or not user.role:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
    request.state.user = user
    return user


def require_permissions(*perms: Permission):
    def _checker(user=Depends(get_current_user)):
        if user.role == "admin":
            return user
        required = set(perms)
        overrides = get_user_overrides(user.user_id)
        if overrides:
            allowed = overrides
            if not required.issubset(allowed):
                missing = ", ".join(p.value for p in (required - allowed))
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Missing permissions: {missing}",
                )
            return user
        if not role_has_permissions(user.role, required):
            missing = ", ".join(p.value for p in required)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Missing: {missing}",
            )
        return user

    return _checker
