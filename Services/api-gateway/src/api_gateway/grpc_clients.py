from __future__ import annotations

import os
import time

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

T = TypeVar("T")


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


def call_idempotent(
    fn: Callable[..., T],
    request,
    *,
    timeout: float,
    metadata=None,
) -> T:
    attempts = _retry_attempts()
    for attempt in range(1, attempts + 1):
        try:
            return fn(request, timeout=timeout, metadata=metadata)
        except grpc.RpcError as exc:
            if attempt >= attempts or exc.code() not in _RETRYABLE_STATUS:
                raise
            time.sleep(_retry_backoff_seconds(attempt))
    raise RuntimeError("unreachable")


@contextmanager
def customer_stub() -> Iterator[customer_pb2_grpc.CustomerServiceStub]:
    channel = grpc.insecure_channel(_addr("CUSTOMER_GRPC_ADDR", "customer-service:50052"))
    try:
        yield customer_pb2_grpc.CustomerServiceStub(channel)
    finally:
        channel.close()


@contextmanager
def product_stub() -> Iterator[product_pb2_grpc.ProductServiceStub]:
    channel = grpc.insecure_channel(_addr("PRODUCT_GRPC_ADDR", "product-service:50053"))
    try:
        yield product_pb2_grpc.ProductServiceStub(channel)
    finally:
        channel.close()


@contextmanager
def warehouse_stub() -> Iterator[warehouse_pb2_grpc.WarehouseServiceStub]:
    channel = grpc.insecure_channel(_addr("WAREHOUSE_GRPC_ADDR", "warehouse-service:50054"))
    try:
        yield warehouse_pb2_grpc.WarehouseServiceStub(channel)
    finally:
        channel.close()


@contextmanager
def warehouse_ops_stub() -> Iterator[warehouse_pb2_grpc.WarehouseOperationsServiceStub]:
    channel = grpc.insecure_channel(_addr("WAREHOUSE_GRPC_ADDR", "warehouse-service:50054"))
    try:
        yield warehouse_pb2_grpc.WarehouseOperationsServiceStub(channel)
    finally:
        channel.close()


@contextmanager
def inventory_stub() -> Iterator[inventory_pb2_grpc.InventoryServiceStub]:
    channel = grpc.insecure_channel(_addr("INVENTORY_GRPC_ADDR", "inventory-service:50055"))
    try:
        yield inventory_pb2_grpc.InventoryServiceStub(channel)
    finally:
        channel.close()


@contextmanager
def documents_stub() -> Iterator[documents_pb2_grpc.DocumentsServiceStub]:
    channel = grpc.insecure_channel(_addr("DOCUMENTS_GRPC_ADDR", "documents-service:50056"))
    try:
        yield documents_pb2_grpc.DocumentsServiceStub(channel)
    finally:
        channel.close()


@contextmanager
def audit_stub() -> Iterator[audit_pb2_grpc.AuditServiceStub]:
    channel = grpc.insecure_channel(_addr("AUDIT_GRPC_ADDR", "audit-service:50057"))
    try:
        yield audit_pb2_grpc.AuditServiceStub(channel)
    finally:
        channel.close()


@contextmanager
def reporting_stub() -> Iterator[reporting_pb2_grpc.ReportingServiceStub]:
    channel = grpc.insecure_channel(_addr("REPORTING_GRPC_ADDR", "reporting-service:50058"))
    try:
        yield reporting_pb2_grpc.ReportingServiceStub(channel)
    finally:
        channel.close()


@contextmanager
def ai_stub() -> Iterator[ai_pb2_grpc.AIServiceStub]:
    channel = grpc.insecure_channel(_addr("AI_GRPC_ADDR", "ai-service:50059"))
    try:
        yield ai_pb2_grpc.AIServiceStub(channel)
    finally:
        channel.close()
