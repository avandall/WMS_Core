from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import grpc
from app.shared.core.database import init_db
from shared_utils.observability import grpc_observability_interceptor
from shared_utils.security import add_configured_grpc_port

from customer_service.grpc_servicer import CustomerServiceServicer
from customer_service.grpc_servicer import add_CustomerServiceServicer_to_server
from customer_service.event_consumer import start_customer_purchase_consumer_thread


def serve(*, host: str = "0.0.0.0", port: int = 50052) -> None:
    init_db()
    start_customer_purchase_consumer_thread()
    server = grpc.server(
        ThreadPoolExecutor(max_workers=10),
        interceptors=[grpc_observability_interceptor(service="customer-service")],
    )
    add_CustomerServiceServicer_to_server(CustomerServiceServicer(), server)
    add_configured_grpc_port(server, host, port)
    server.start()
    server.wait_for_termination()
