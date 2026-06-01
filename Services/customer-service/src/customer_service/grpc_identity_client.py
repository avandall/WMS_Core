from __future__ import annotations

import os
from dataclasses import dataclass

from shared_utils.security import configured_grpc_channel

from customer_service.gen.wms.identity.v1 import identity_pb2, identity_pb2_grpc


@dataclass(slots=True)
class IdentityUser:
    user_id: int
    email: str
    full_name: str
    role: str
    is_active: bool


def _identity_addr() -> str:
    return os.getenv("IDENTITY_GRPC_ADDR", "identity-service:50051")


def validate_token(access_token: str, *, request_id: str | None = None) -> IdentityUser | None:
    metadata = [("x-request-id", request_id)] if request_id else None
    with configured_grpc_channel(_identity_addr()) as channel:
        stub = identity_pb2_grpc.IdentityServiceStub(channel)
        resp = stub.ValidateToken(
            identity_pb2.ValidateTokenRequest(access_token=access_token),
            timeout=5,
            metadata=metadata,
        )
        if not resp.valid:
            return None
        return IdentityUser(
            user_id=int(resp.user_id),
            email=resp.email,
            full_name=resp.full_name,
            role=resp.role,
            is_active=bool(resp.is_active),
        )
