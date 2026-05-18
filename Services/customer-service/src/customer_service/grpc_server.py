from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import grpc

from customer_service.grpc_servicer import CustomerServiceServicer
from customer_service.grpc_servicer import add_CustomerServiceServicer_to_server


def serve(*, host: str = "0.0.0.0", port: int = 50052) -> None:
    server = grpc.server(ThreadPoolExecutor(max_workers=10))
    add_CustomerServiceServicer_to_server(CustomerServiceServicer(), server)
    server.add_insecure_port(f"{host}:{port}")
    server.start()
    server.wait_for_termination()

