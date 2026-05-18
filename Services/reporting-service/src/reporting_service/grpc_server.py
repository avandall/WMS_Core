from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import grpc
from shared_utils.observability import grpc_observability_interceptor

from reporting_service.grpc_servicer import ReportingServiceServicer
from reporting_service.grpc_servicer import add_ReportingServiceServicer_to_server


def serve(*, host: str = "0.0.0.0", port: int = 50058) -> None:
    server = grpc.server(
        ThreadPoolExecutor(max_workers=10),
        interceptors=[grpc_observability_interceptor(service="reporting-service")],
    )
    add_ReportingServiceServicer_to_server(ReportingServiceServicer(), server)
    server.add_insecure_port(f"{host}:{port}")
    server.start()
    server.wait_for_termination()
