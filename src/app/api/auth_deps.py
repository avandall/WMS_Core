"""Authentication dependencies for FastAPI routes."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt

from app.core.auth import decode_token
from app.core.permissions import Permission, role_has_permissions
from app.core.permissions_store import get_user_overrides
from app.core.settings import settings
from app.domain.entities.user import User
from app.infrastructure.persistence.repositories.user_repo import UserRepo
from app.core.database import get_session
from app.application.services.user_service import UserService


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db=Depends(get_session),
):
    if settings.testing:
        test_user = User(
            user_id=1,
            email="test-admin@example.com",
            hashed_password="not-used-in-testing",
            role="admin",
            full_name="Test Admin",
            is_active=True,
        )
        request.state.user = test_user
        return test_user

    if not creds:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    token = creds.credentials
    try:
        payload = decode_token(token)
        user_id = int(payload.get("sub"))
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    service = UserService(UserRepo(db))
    user = service.get_user(user_id)
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
    request.state.user = user
    return user


def require_admin(user=Depends(get_current_user)):
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
    return user


def require_permissions(*perms: Permission):
    """Dependency factory enforcing that current user has all required permissions."""

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

