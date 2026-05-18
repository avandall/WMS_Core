from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import grpc

from identity_service.grpc_servicer import IdentityServiceServicer
from identity_service.grpc_servicer import add_IdentityServiceServicer_to_server


def serve(*, host: str = "0.0.0.0", port: int = 50051) -> None:
    server = grpc.server(ThreadPoolExecutor(max_workers=10))
    add_IdentityServiceServicer_to_server(IdentityServiceServicer(), server)
    server.add_insecure_port(f"{host}:{port}")
    server.start()
    server.wait_for_termination()

