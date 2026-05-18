"""Auth dependencies for services (delegates auth to Identity Service)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest, urlopen

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.shared.core.permissions import Permission, role_has_permissions
from app.shared.core.permissions_store import get_user_overrides


bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(slots=True)
class CurrentUser:
    user_id: int
    role: str
    is_active: bool = True


def _identity_base_url() -> str:
    return os.getenv("IDENTITY_SERVICE_URL", "http://identity-service:8001").rstrip("/")


def _fetch_me(token: str) -> dict:
    url = f"{_identity_base_url()}/api/v1/users/me"
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
):
    if not creds:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    me = _fetch_me(creds.credentials)
    user = CurrentUser(
        user_id=int(me.get("user_id") or me.get("id") or me.get("userId") or 0),
        role=str(me.get("role") or ""),
        is_active=bool(me.get("is_active", True)),
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

