from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import grpc

from documents_service.grpc_servicer import DocumentsServiceServicer
from documents_service.grpc_servicer import add_DocumentsServiceServicer_to_server


def serve(*, host: str = "0.0.0.0", port: int = 50056) -> None:
    server = grpc.server(ThreadPoolExecutor(max_workers=10))
    add_DocumentsServiceServicer_to_server(DocumentsServiceServicer(), server)
    server.add_insecure_port(f"{host}:{port}")
    server.start()
    server.wait_for_termination()

