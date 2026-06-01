from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import grpc
from app.shared.core.database import init_db
from shared_utils.observability import grpc_observability_interceptor
from shared_utils.security import add_configured_grpc_port

from documents_service.grpc_servicer import DocumentsServiceServicer
from documents_service.grpc_servicer import add_DocumentsServiceServicer_to_server


def serve(*, host: str = "0.0.0.0", port: int = 50056) -> None:
    init_db()
    server = grpc.server(
        ThreadPoolExecutor(max_workers=10),
        interceptors=[grpc_observability_interceptor(service="documents-service")],
    )
    add_DocumentsServiceServicer_to_server(DocumentsServiceServicer(), server)
    add_configured_grpc_port(server, host, port)
    server.start()
    server.wait_for_termination()
