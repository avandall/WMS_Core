"""Authentication dependencies for FastAPI routes."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status, WebSocket, WebSocketException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt

from app.shared.core.auth import decode_token
from app.shared.core.permissions import Permission, role_has_permissions
from app.shared.core.permissions_store import get_user_overrides
from app.shared.core.settings import settings
from app.shared.core.logging import get_logger
from app.shared.core.session import session_manager
from app.modules.users.domain.entities.user import User
from app.modules.users.infrastructure.repositories.user_repo import UserRepo
from app.shared.core.database import get_session
from app.modules.users.application.services.user_service import UserService

logger = get_logger(__name__)


bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
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

    # Prefer Redis-based token cache to avoid repeated SQL hits
    cached_data = await session_manager.get_token_session(token)
    if cached_data:
        user = User(
            user_id=int(cached_data["user_id"]),
            email=cached_data["email"],
            hashed_password="",  # not needed for auth flow
            role=cached_data["role"],
            full_name=cached_data.get("full_name"),
            is_active=cached_data.get("is_active", True),
        )
    else:
        service = UserService(UserRepo(db))
        user = await service.get_user(user_id)
        if user.is_active:
            token_cache_data = {
                "user_id": user.user_id,
                "email": user.email,
                "role": user.role,
                "full_name": user.full_name,
                "is_active": user.is_active,
            }
            await session_manager.create_token_session(token, token_cache_data, ex=settings.access_token_expire_minutes * 60)

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


async def get_current_user_ws(websocket: WebSocket):
    """WebSocket-specific authentication that extracts token from headers."""
    if settings.testing:
        test_user = User(
            user_id=1,
            email="test-admin@example.com",
            hashed_password="not-used-in-testing",
            role="admin",
            full_name="Test Admin",
            is_active=True,
        )
        return test_user

    # Extract token from Authorization header (preferred method)
    auth_header = websocket.headers.get("authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]  # Remove "Bearer " prefix
    else:
        # Fallback to query params for compatibility (but log warning)
        token = websocket.query_params.get("token")
        if token:
            logger.warning("WebSocket token passed via query params - insecure, use Authorization header instead")
    
    if not token:
        raise WebSocketException(code=1008, reason="Not authenticated: token required in Authorization header")

    try:
        payload = decode_token(token)
        user_id = int(payload.get("sub"))
    except jwt.PyJWTError:
        raise WebSocketException(code=1008, reason="Invalid token")

    cached_data = await session_manager.get_token_session(token)
    if cached_data:
        user = User(
            user_id=int(cached_data["user_id"]),
            email=cached_data["email"],
            hashed_password="",
            role=cached_data["role"],
            full_name=cached_data.get("full_name"),
            is_active=cached_data.get("is_active", True),
        )
        if not user.is_active:
            raise WebSocketException(code=1008, reason="Inactive user")
        return user

    # Use short-lived DB session for authentication only
    from app.shared.core.database import SessionLocal
    db = SessionLocal()
    try:
        service = UserService(UserRepo(db))
        user = await service.get_user(user_id)
        if not user.is_active:
            raise WebSocketException(code=1008, reason="Inactive user")

        token_cache_data = {
            "user_id": user.user_id,
            "email": user.email,
            "role": user.role,
            "full_name": user.full_name,
            "is_active": user.is_active,
        }
        await session_manager.create_token_session(token, token_cache_data, ex=settings.access_token_expire_minutes * 60)
        return user
    finally:
        db.close()

