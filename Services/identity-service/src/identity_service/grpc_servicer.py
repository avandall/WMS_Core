from __future__ import annotations

import os
import asyncio

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

        # Log incoming ValidateToken call for debugging
        try:
            import json
            request_id = None
            for k, v in context.invocation_metadata() or []:
                if k.lower() == "x-request-id":
                    request_id = v
            print(json.dumps({"msg": "validate_token_received", "request_id": request_id, "token_len": len(token)}))
        except Exception:
            pass

        # In this codebase, decode_token validates signature/exp.
        try:
            payload = decode_token(token)
            user_id = int(payload.get("sub") or 0)
            if not user_id:
                return identity_pb2.ValidateTokenResponse(valid=False)
        except Exception:
            return identity_pb2.ValidateTokenResponse(valid=False)

        # Resolve current user from the identity datastore.
        # Note: `get_session()` is a FastAPI dependency generator; here we call next() to get a session.
        session_gen = get_session()
        db = next(session_gen)
        try:
            service = UserService(UserRepo(db))
            user = asyncio.run(service.get_user(user_id))
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

    def CreateUser(self, request: identity_pb2.CreateUserRequest, context: grpc.ServicerContext):
        email = request.email
        password = request.password
        role = request.role or "user"
        full_name = request.full_name or ""

        if not email or not password:
            return identity_pb2.CreateUserResponse(success=False, message="Email and password are required")

        session_gen = get_session()
        db = next(session_gen)
        try:
            service = UserService(UserRepo(db))
            # Create user using the service
            user = asyncio.run(service.create_user(email, password, role, full_name))
            return identity_pb2.CreateUserResponse(
                success=True,
                message="User created successfully",
                user_id=int(user.user_id),
            )
        except Exception as e:
            return identity_pb2.CreateUserResponse(success=False, message=str(e))
        finally:
            try:
                db.close()
            except Exception:
                pass

    def DeleteUser(self, request: identity_pb2.DeleteUserRequest, context: grpc.ServicerContext):
        user_id = request.user_id
        if not user_id:
            return identity_pb2.DeleteUserResponse(success=False, message="User ID is required")

        session_gen = get_session()
        db = next(session_gen)
        try:
            service = UserService(UserRepo(db))
            asyncio.run(service.delete_user(user_id))
            return identity_pb2.DeleteUserResponse(success=True, message="User deleted successfully")
        except Exception as e:
            return identity_pb2.DeleteUserResponse(success=False, message=str(e))
        finally:
            try:
                db.close()
            except Exception:
                pass

    def ListUsers(self, request: identity_pb2.ListUsersRequest, context: grpc.ServicerContext):
        session_gen = get_session()
        db = next(session_gen)
        try:
            service = UserService(UserRepo(db))
            users = asyncio.run(service.list_users())
            entries = []
            for u in (users.values() if isinstance(users, dict) else users):
                entries.append(identity_pb2.UserEntry(
                    user_id=int(u.user_id),
                    email=u.email or "",
                    role=u.role or "",
                    full_name=u.full_name or "",
                    is_active=bool(u.is_active),
                ))
            return identity_pb2.ListUsersResponse(users=entries)
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return identity_pb2.ListUsersResponse()
        finally:
            try:
                db.close()
            except Exception:
                pass


# Convenience re-export so grpc_server can import without depending on generated module naming.
add_IdentityServiceServicer_to_server = identity_pb2_grpc.add_IdentityServiceServicer_to_server
