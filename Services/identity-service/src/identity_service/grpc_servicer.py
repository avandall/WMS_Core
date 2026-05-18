from __future__ import annotations

import os

import grpc

from app.modules.users.application.services.user_service import UserService
from app.modules.users.infrastructure.repositories.user_repo import UserRepo
from app.shared.core.auth import decode_token
from app.shared.core.database import get_session

from identity_service.gen.wms.identity.v1 import identity_pb2, identity_pb2_grpc


class IdentityServiceServicer(identity_pb2_grpc.IdentityServiceServicer):
    def ValidateToken(self, request: identity_pb2.ValidateTokenRequest, context: grpc.ServicerContext):
        token = request.access_token
        if not token:
            return identity_pb2.ValidateTokenResponse(valid=False)

        # In this codebase, decode_token validates signature/exp.
        try:
            payload = decode_token(token)
            user_id = int(payload.get("sub") or 0)
            if not user_id:
                return identity_pb2.ValidateTokenResponse(valid=False)
        except Exception:
            return identity_pb2.ValidateTokenResponse(valid=False)

        # Resolve current user from DB (same as monolith behavior).
        # Note: `get_session()` is a FastAPI dependency generator; here we call next() to get a session.
        session_gen = get_session()
        db = next(session_gen)
        try:
            service = UserService(UserRepo(db))
            user = service.get_user(user_id)
            return identity_pb2.ValidateTokenResponse(
                valid=True,
                user_id=int(user.user_id),
                email=user.email,
                full_name=user.full_name or "",
                role=user.role,
                is_active=bool(user.is_active),
            )
        except Exception:
            return identity_pb2.ValidateTokenResponse(valid=False)
        finally:
            try:
                db.close()
            except Exception:
                pass


# Convenience re-export so grpc_server can import without depending on generated module naming.
add_IdentityServiceServicer_to_server = identity_pb2_grpc.add_IdentityServiceServicer_to_server

