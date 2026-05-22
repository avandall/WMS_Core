from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import grpc
from shared_utils.observability import grpc_observability_interceptor
from shared_utils.security import add_configured_grpc_port

from ai_service.grpc_servicer import AIServiceServicer
from ai_service.grpc_servicer import add_AIServiceServicer_to_server


def serve(*, host: str = "0.0.0.0", port: int = 50059) -> None:
    server = grpc.server(
        ThreadPoolExecutor(max_workers=10),
        interceptors=[grpc_observability_interceptor(service="ai-service")],
    )
    add_AIServiceServicer_to_server(AIServiceServicer(), server)
    add_configured_grpc_port(server, host, port)
    server.start()
    server.wait_for_termination()
