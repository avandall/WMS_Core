"""Authentication dependencies for FastAPI routes."""

from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest, urlopen

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt

from app.shared.core.auth import decode_token
from app.shared.core.permissions import Permission, role_has_permissions
from app.shared.core.permissions_store import get_user_overrides
from app.shared.core.settings import settings
from app.modules.users.domain.entities.user import User
from app.modules.users.infrastructure.repositories.user_repo import UserRepo
from app.shared.core.database import get_session
from app.modules.users.application.services.user_service import UserService


bearer_scheme = HTTPBearer(auto_error=False)


def _identity_base_url() -> str | None:
    url = os.getenv("IDENTITY_SERVICE_URL")
    return url.rstrip("/") if url else None


def _fetch_identity_me(token: str) -> dict:
    base = _identity_base_url()
    if not base:
        raise RuntimeError("IDENTITY_SERVICE_URL not set")
    url = f"{base}/api/v1/users/me"
    req = UrlRequest(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        raise HTTPException(status_code=exc.code, detail="Not authenticated") from exc
    except URLError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Identity service unavailable",
        ) from exc


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
    identity_base = _identity_base_url()
    if identity_base:
        me = _fetch_identity_me(token)
        user = User(
            user_id=int(me.get("user_id") or me.get("id") or me.get("userId") or 0),
            email=str(me.get("email") or ""),
            hashed_password="",
            role=str(me.get("role") or ""),
            full_name=str(me.get("full_name") or me.get("fullName") or ""),
            is_active=bool(me.get("is_active", True)),
        )
        if not user.user_id or not user.role:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    else:
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
