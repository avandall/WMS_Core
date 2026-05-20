from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import grpc
from app.shared.core.database import init_db
from shared_utils.observability import grpc_observability_interceptor

from customer_service.grpc_servicer import CustomerServiceServicer
from customer_service.grpc_servicer import add_CustomerServiceServicer_to_server


def serve(*, host: str = "0.0.0.0", port: int = 50052) -> None:
    init_db()
    server = grpc.server(
        ThreadPoolExecutor(max_workers=10),
        interceptors=[grpc_observability_interceptor(service="customer-service")],
    )
    add_CustomerServiceServicer_to_server(CustomerServiceServicer(), server)
    server.add_insecure_port(f"{host}:{port}")
    server.start()
    server.wait_for_termination()
