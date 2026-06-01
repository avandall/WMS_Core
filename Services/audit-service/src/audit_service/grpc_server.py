from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import grpc
from app.shared.core.database import init_db
from shared_utils.observability import grpc_observability_interceptor
from shared_utils.security import add_configured_grpc_port

from audit_service.event_consumer import start_audit_event_consumer_thread
from audit_service.grpc_servicer import AuditServiceServicer
from audit_service.grpc_servicer import add_AuditServiceServicer_to_server


def serve(*, host: str = "0.0.0.0", port: int = 50057) -> None:
    init_db()
    start_audit_event_consumer_thread()
    server = grpc.server(
        ThreadPoolExecutor(max_workers=10),
        interceptors=[grpc_observability_interceptor(service="audit-service")],
    )
    add_AuditServiceServicer_to_server(AuditServiceServicer(), server)
    add_configured_grpc_port(server, host, port)
    server.start()
    server.wait_for_termination()
