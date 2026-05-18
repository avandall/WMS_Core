from __future__ import annotations

import os

import grpc

from contextlib import contextmanager
from typing import Iterator

from api_gateway.gen.wms.customer.v1 import customer_pb2_grpc
from api_gateway.gen.wms.inventory.v1 import inventory_pb2_grpc
from api_gateway.gen.wms.product.v1 import product_pb2_grpc
from api_gateway.gen.wms.warehouse.v1 import warehouse_pb2_grpc
from api_gateway.gen.wms.documents.v1 import documents_pb2_grpc


def _addr(env: str, default: str) -> str:
    return os.getenv(env, default)


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
