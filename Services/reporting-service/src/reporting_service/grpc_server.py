from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import grpc
from app.shared.core.database import init_db
from shared_utils.observability import grpc_observability_interceptor
from shared_utils.security import add_configured_grpc_port

from reporting_service.grpc_servicer import ReportingServiceServicer
from reporting_service.grpc_servicer import add_ReportingServiceServicer_to_server


def serve(*, host: str = "0.0.0.0", port: int = 50058) -> None:
    init_db()
    server = grpc.server(
        ThreadPoolExecutor(max_workers=10),
        interceptors=[grpc_observability_interceptor(service="reporting-service")],
    )
    add_ReportingServiceServicer_to_server(ReportingServiceServicer(), server)
    add_configured_grpc_port(server, host, port)
    server.start()
    server.wait_for_termination()
