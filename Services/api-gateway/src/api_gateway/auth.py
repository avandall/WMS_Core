from __future__ import annotations

import os
from dataclasses import dataclass

import grpc
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api_gateway.gen.wms.identity.v1 import identity_pb2, identity_pb2_grpc


bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(slots=True)
class CurrentUser:
    user_id: int
    role: str
    email: str = ""
    full_name: str = ""
    is_active: bool = True


def _identity_addr() -> str:
    return os.getenv("IDENTITY_GRPC_ADDR", "identity-service:50051")


def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> CurrentUser:
    if not creds:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    token = creds.credentials
    with grpc.insecure_channel(_identity_addr()) as channel:
        stub = identity_pb2_grpc.IdentityServiceStub(channel)
        resp = stub.ValidateToken(identity_pb2.ValidateTokenRequest(access_token=token), timeout=5)
    if not resp.valid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = CurrentUser(
        user_id=int(resp.user_id),
        role=resp.role,
        email=resp.email,
        full_name=resp.full_name,
        is_active=bool(resp.is_active),
    )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
    request.state.user = user
    return user

