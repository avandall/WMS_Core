from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass

import grpc

from contextlib import contextmanager
from typing import Callable, Iterator, TypeVar

from api_gateway.gen.wms.customer.v1 import customer_pb2_grpc
from api_gateway.gen.wms.inventory.v1 import inventory_pb2_grpc
from api_gateway.gen.wms.product.v1 import product_pb2_grpc
from api_gateway.gen.wms.warehouse.v1 import warehouse_pb2_grpc
from api_gateway.gen.wms.documents.v1 import documents_pb2_grpc
from api_gateway.gen.wms.audit.v1 import audit_pb2_grpc
from api_gateway.gen.wms.reporting.v1 import reporting_pb2_grpc
from api_gateway.gen.wms.ai.v1 import ai_pb2_grpc
from api_gateway.gen.wms.identity.v1 import identity_pb2_grpc

# ... rest of file ...

@contextmanager
def identity_stub() -> Iterator[identity_pb2_grpc.IdentityServiceStub]:
    channel = configured_grpc_channel(_addr("IDENTITY_GRPC_ADDR", "identity-service:50051"))
    try:
        yield identity_pb2_grpc.IdentityServiceStub(channel)
    finally:
        channel.close()
from api_gateway.grpc_security import configured_grpc_channel

T = TypeVar("T")


class CircuitOpenError(grpc.RpcError):
    def __init__(self, key: str):
        self.key = key

    def code(self) -> grpc.StatusCode:
        return grpc.StatusCode.UNAVAILABLE

    def details(self) -> str:
        return f"Circuit open for downstream gRPC method: {self.key}"


def _addr(env: str, default: str) -> str:
    return os.getenv(env, default)


def _retry_attempts() -> int:
    try:
        return max(1, int(os.getenv("GRPC_RETRY_ATTEMPTS", "2")))
    except ValueError:
        return 2


def _retry_backoff_seconds(attempt: int) -> float:
    try:
        base = max(0.0, float(os.getenv("GRPC_RETRY_BACKOFF_SECONDS", "0.05")))
    except ValueError:
        base = 0.05
    return base * (2 ** max(0, attempt - 1))


_RETRYABLE_STATUS = {
    grpc.StatusCode.UNAVAILABLE,
    grpc.StatusCode.DEADLINE_EXCEEDED,
    grpc.StatusCode.RESOURCE_EXHAUSTED,
}


@dataclass(slots=True)
class _CircuitState:
    failures: int = 0
    open_until: float = 0.0


_circuit_lock = threading.Lock()
_circuit_state: dict[str, _CircuitState] = {}


def _circuit_threshold() -> int:
    try:
        return max(0, int(os.getenv("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "5")))
    except ValueError:
        return 5


def _circuit_recovery_seconds() -> float:
    try:
        return max(0.0, float(os.getenv("CIRCUIT_BREAKER_RECOVERY_SECONDS", "15")))
    except ValueError:
        return 15.0


def _circuit_key(fn: Callable[..., object]) -> str:
    method = getattr(fn, "_method", None)
    if isinstance(method, bytes):
        return method.decode("utf-8", errors="replace")
    if method:
        return str(method)
    return getattr(fn, "__name__", repr(fn))


def _circuit_before_call(key: str) -> None:
    if _circuit_threshold() <= 0:
        return
    now = time.monotonic()
    with _circuit_lock:
        state = _circuit_state.get(key)
        if state and state.open_until > now:
            raise CircuitOpenError(key)


def _circuit_record_success(key: str) -> None:
    with _circuit_lock:
        _circuit_state.pop(key, None)


def _circuit_record_failure(key: str) -> None:
    threshold = _circuit_threshold()
    if threshold <= 0:
        return
    with _circuit_lock:
        state = _circuit_state.setdefault(key, _CircuitState())
        state.failures += 1
        if state.failures >= threshold:
            state.open_until = time.monotonic() + _circuit_recovery_seconds()


def call_idempotent(
    fn: Callable[..., T],
    request,
    *,
    timeout: float,
    metadata=None,
) -> T:
    attempts = _retry_attempts()
    circuit_key = _circuit_key(fn)
    for attempt in range(1, attempts + 1):
        _circuit_before_call(circuit_key)
        try:
            response = fn(request, timeout=timeout, metadata=metadata)
            _circuit_record_success(circuit_key)
            return response
        except grpc.RpcError as exc:
            if attempt >= attempts or exc.code() not in _RETRYABLE_STATUS:
                if exc.code() in _RETRYABLE_STATUS:
                    _circuit_record_failure(circuit_key)
                raise
            _circuit_record_failure(circuit_key)
            time.sleep(_retry_backoff_seconds(attempt))
    raise RuntimeError("unreachable")


@contextmanager
def customer_stub() -> Iterator[customer_pb2_grpc.CustomerServiceStub]:
    channel = configured_grpc_channel(_addr("CUSTOMER_GRPC_ADDR", "customer-service:50052"))
    try:
        yield customer_pb2_grpc.CustomerServiceStub(channel)
    finally:
        channel.close()


@contextmanager
def product_stub() -> Iterator[product_pb2_grpc.ProductServiceStub]:
    channel = configured_grpc_channel(_addr("PRODUCT_GRPC_ADDR", "product-service:50053"))
    try:
        yield product_pb2_grpc.ProductServiceStub(channel)
    finally:
        channel.close()


@contextmanager
def warehouse_stub() -> Iterator[warehouse_pb2_grpc.WarehouseServiceStub]:
    channel = configured_grpc_channel(_addr("WAREHOUSE_GRPC_ADDR", "warehouse-service:50054"))
    try:
        yield warehouse_pb2_grpc.WarehouseServiceStub(channel)
    finally:
        channel.close()


@contextmanager
def warehouse_ops_stub() -> Iterator[warehouse_pb2_grpc.WarehouseOperationsServiceStub]:
    channel = configured_grpc_channel(_addr("WAREHOUSE_GRPC_ADDR", "warehouse-service:50054"))
    try:
        yield warehouse_pb2_grpc.WarehouseOperationsServiceStub(channel)
    finally:
        channel.close()


@contextmanager
def inventory_stub() -> Iterator[inventory_pb2_grpc.InventoryServiceStub]:
    channel = configured_grpc_channel(_addr("INVENTORY_GRPC_ADDR", "inventory-service:50055"))
    try:
        yield inventory_pb2_grpc.InventoryServiceStub(channel)
    finally:
        channel.close()


@contextmanager
def documents_stub() -> Iterator[documents_pb2_grpc.DocumentsServiceStub]:
    channel = configured_grpc_channel(_addr("DOCUMENTS_GRPC_ADDR", "documents-service:50056"))
    try:
        yield documents_pb2_grpc.DocumentsServiceStub(channel)
    finally:
        channel.close()


@contextmanager
def audit_stub() -> Iterator[audit_pb2_grpc.AuditServiceStub]:
    channel = configured_grpc_channel(_addr("AUDIT_GRPC_ADDR", "audit-service:50057"))
    try:
        yield audit_pb2_grpc.AuditServiceStub(channel)
    finally:
        channel.close()


@contextmanager
def reporting_stub() -> Iterator[reporting_pb2_grpc.ReportingServiceStub]:
    channel = configured_grpc_channel(_addr("REPORTING_GRPC_ADDR", "reporting-service:50058"))
    try:
        yield reporting_pb2_grpc.ReportingServiceStub(channel)
    finally:
        channel.close()


@contextmanager
def ai_stub() -> Iterator[ai_pb2_grpc.AIServiceStub]:
    channel = configured_grpc_channel(_addr("AI_GRPC_ADDR", "ai-service:50059"))
    try:
        yield ai_pb2_grpc.AIServiceStub(channel)
    finally:
        channel.close()
