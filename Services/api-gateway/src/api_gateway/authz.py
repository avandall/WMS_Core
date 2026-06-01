from __future__ import annotations

from fastapi import Depends, HTTPException, status

from api_gateway.auth import CurrentUser, get_current_user
from api_gateway.permissions import Permission, role_has_permissions


def require_permissions(*perms: Permission):
    required = set(perms)

    def _checker(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role == "admin":
            return user
        if not role_has_permissions(user.role, required):
            missing = ", ".join(p.value for p in required)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Missing: {missing}",
            )
        return user

    return _checker

