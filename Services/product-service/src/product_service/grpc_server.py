from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import grpc

from product_service.grpc_servicer import ProductServiceServicer
from product_service.grpc_servicer import add_ProductServiceServicer_to_server


def serve(*, host: str = "0.0.0.0", port: int = 50053) -> None:
    server = grpc.server(ThreadPoolExecutor(max_workers=10))
    add_ProductServiceServicer_to_server(ProductServiceServicer(), server)
    server.add_insecure_port(f"{host}:{port}")
    server.start()
    server.wait_for_termination()

