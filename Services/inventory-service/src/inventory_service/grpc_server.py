from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import grpc

from inventory_service.grpc_servicer import InventoryServiceServicer
from inventory_service.grpc_servicer import add_InventoryServiceServicer_to_server


def serve(*, host: str = "0.0.0.0", port: int = 50055) -> None:
    server = grpc.server(ThreadPoolExecutor(max_workers=10))
    add_InventoryServiceServicer_to_server(InventoryServiceServicer(), server)
    server.add_insecure_port(f"{host}:{port}")
    server.start()
    server.wait_for_termination()

