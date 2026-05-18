from __future__ import annotations

import time
from collections.abc import Callable

import grpc

from .http import METRICS, json_log


class GrpcObservabilityInterceptor(grpc.ServerInterceptor):
    def __init__(self, *, service: str) -> None:
        self.service = service

    def intercept_service(self, continuation: Callable, handler_call_details):
        handler = continuation(handler_call_details)
        if handler is None or handler.unary_unary is None:
            return handler

        method = handler_call_details.method

        def unary_unary(request, context):
            request_id = _request_id(context)
            start = time.monotonic()
            status = "OK"
            try:
                return handler.unary_unary(request, context)
            except Exception as exc:
                status = _grpc_error_name(exc)
                json_log(
                    service=self.service,
                    level="error",
                    message="grpc_request_failed",
                    request_id=request_id,
                    method=method,
                    error=type(exc).__name__,
                    grpc_status=status,
                )
                raise
            finally:
                duration_ms = (time.monotonic() - start) * 1000.0
                METRICS.observe(method="GRPC", path=method, status=0 if status == "OK" else 1, duration_ms=duration_ms)
                json_log(
                    service=self.service,
                    level="info",
                    message="grpc_request",
                    request_id=request_id,
                    method=method,
                    grpc_status=status,
                    duration_ms=duration_ms,
                )

        return grpc.unary_unary_rpc_method_handler(
            unary_unary,
            request_deserializer=handler.request_deserializer,
            response_serializer=handler.response_serializer,
        )


def grpc_observability_interceptor(*, service: str) -> GrpcObservabilityInterceptor:
    return GrpcObservabilityInterceptor(service=service)


def _request_id(context: grpc.ServicerContext) -> str | None:
    for key, value in context.invocation_metadata() or []:
        if key.lower() == "x-request-id":
            return value
    return None


def _grpc_error_name(exc: Exception) -> str:
    if isinstance(exc, grpc.RpcError):
        try:
            return exc.code().name
        except Exception:
            return grpc.StatusCode.UNKNOWN.name
    return grpc.StatusCode.UNKNOWN.name
