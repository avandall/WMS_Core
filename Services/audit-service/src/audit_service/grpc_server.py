from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import grpc

from audit_service.grpc_servicer import AuditServiceServicer
from audit_service.grpc_servicer import add_AuditServiceServicer_to_server


def serve(*, host: str = "0.0.0.0", port: int = 50057) -> None:
    server = grpc.server(ThreadPoolExecutor(max_workers=10))
    add_AuditServiceServicer_to_server(AuditServiceServicer(), server)
    server.add_insecure_port(f"{host}:{port}")
    server.start()
    server.wait_for_termination()

