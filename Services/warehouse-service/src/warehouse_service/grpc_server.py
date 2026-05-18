from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import grpc

from warehouse_service.grpc_servicer import (
    WarehouseOperationsServiceServicer,
    WarehouseServiceServicer,
    add_WarehouseOperationsServiceServicer_to_server,
    add_WarehouseServiceServicer_to_server,
)


def serve(*, host: str = "0.0.0.0", port: int = 50054) -> None:
    server = grpc.server(ThreadPoolExecutor(max_workers=10))
    add_WarehouseServiceServicer_to_server(WarehouseServiceServicer(), server)
    add_WarehouseOperationsServiceServicer_to_server(WarehouseOperationsServiceServicer(), server)
    server.add_insecure_port(f"{host}:{port}")
    server.start()
    server.wait_for_termination()

