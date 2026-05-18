from __future__ import annotations

import grpc
from fastapi import HTTPException, status


_GRPC_HTTP_STATUS = {
    grpc.StatusCode.INVALID_ARGUMENT: status.HTTP_400_BAD_REQUEST,
    grpc.StatusCode.UNAUTHENTICATED: status.HTTP_401_UNAUTHORIZED,
    grpc.StatusCode.PERMISSION_DENIED: status.HTTP_403_FORBIDDEN,
    grpc.StatusCode.NOT_FOUND: status.HTTP_404_NOT_FOUND,
    grpc.StatusCode.ALREADY_EXISTS: status.HTTP_409_CONFLICT,
    grpc.StatusCode.FAILED_PRECONDITION: status.HTTP_409_CONFLICT,
    grpc.StatusCode.RESOURCE_EXHAUSTED: status.HTTP_429_TOO_MANY_REQUESTS,
    grpc.StatusCode.CANCELLED: 499,
    grpc.StatusCode.DEADLINE_EXCEEDED: status.HTTP_504_GATEWAY_TIMEOUT,
    grpc.StatusCode.UNAVAILABLE: status.HTTP_503_SERVICE_UNAVAILABLE,
    grpc.StatusCode.UNIMPLEMENTED: status.HTTP_501_NOT_IMPLEMENTED,
}


def grpc_status_to_http(code: grpc.StatusCode) -> int:
    return _GRPC_HTTP_STATUS.get(code, status.HTTP_502_BAD_GATEWAY)


def grpc_http_exception(exc: grpc.RpcError, *, fallback_detail: str = "Downstream service error") -> HTTPException:
    code = exc.code() if hasattr(exc, "code") else grpc.StatusCode.UNKNOWN
    details = exc.details() if hasattr(exc, "details") else None
    return HTTPException(status_code=grpc_status_to_http(code), detail=details or fallback_detail)
