from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import grpc

from ai_service.grpc_servicer import AIServiceServicer
from ai_service.grpc_servicer import add_AIServiceServicer_to_server


def serve(*, host: str = "0.0.0.0", port: int = 50059) -> None:
    server = grpc.server(ThreadPoolExecutor(max_workers=10))
    add_AIServiceServicer_to_server(AIServiceServicer(), server)
    server.add_insecure_port(f"{host}:{port}")
    server.start()
    server.wait_for_termination()

