from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SHARED_SRC = ROOT / "Libraries" / "shared-utils" / "src"
LOCAL_GRPC_HOST = "127.0.0.1"


@dataclass(frozen=True)
class ServiceSpec:
    name: str
    service_dir: Path
    src_dir: Path
    module: str
    function: str
    grpc_port: int
    db_name: str | None = None
    init_tables: str | None = None
    extra_env: dict[str, str] = field(default_factory=dict)

    @property
    def run_env_var(self) -> str:
        return f"RUN_{self.name.upper().replace('-', '_')}"

    @property
    def database_env_var(self) -> str | None:
        if self.db_name is None:
            return None
        return f"{self.db_name.upper().replace('-', '_')}_DATABASE_URL"

    @property
    def init_tables_env_var(self) -> str | None:
        if self.db_name is None:
            return None
        return f"{self.db_name.upper().replace('-', '_')}_INIT_DB_TABLES"


GRPC_SERVICES: tuple[ServiceSpec, ...] = (
    ServiceSpec(
        name="identity-service",
        service_dir=ROOT / "Services" / "identity-service",
        src_dir=ROOT / "Services" / "identity-service" / "src",
        module="identity_service.main",
        function="main_grpc",
        grpc_port=50051,
        db_name="identity",
        init_tables="users",
    ),
    ServiceSpec(
        name="customer-service",
        service_dir=ROOT / "Services" / "customer-service",
        src_dir=ROOT / "Services" / "customer-service" / "src",
        module="customer_service.main",
        function="main_grpc",
        grpc_port=50052,
        db_name="customer",
        init_tables="customers,customer_purchases",
        extra_env={"CUSTOMER_PURCHASE_CONSUMER_ENABLED": "0"},
    ),
    ServiceSpec(
        name="product-service",
        service_dir=ROOT / "Services" / "product-service",
        src_dir=ROOT / "Services" / "product-service" / "src",
        module="product_service.main",
        function="main_grpc",
        grpc_port=50053,
        db_name="product",
        init_tables="products",
    ),
    ServiceSpec(
        name="warehouse-service",
        service_dir=ROOT / "Services" / "warehouse-service",
        src_dir=ROOT / "Services" / "warehouse-service" / "src",
        module="warehouse_service.main",
        function="main_grpc",
        grpc_port=50054,
        db_name="warehouse",
        init_tables="warehouses,positions",
    ),
    ServiceSpec(
        name="inventory-service",
        service_dir=ROOT / "Services" / "inventory-service",
        src_dir=ROOT / "Services" / "inventory-service" / "src",
        module="inventory_service.main",
        function="main_grpc",
        grpc_port=50055,
        db_name="inventory",
        init_tables="inventory,warehouse_inventory,inventory_movement_ledger",
        extra_env={"INVENTORY_MOVEMENT_CONSUMER_ENABLED": "0"},
    ),
    ServiceSpec(
        name="documents-service",
        service_dir=ROOT / "Services" / "documents-service",
        src_dir=ROOT / "Services" / "documents-service" / "src",
        module="documents_service.main",
        function="main_grpc",
        grpc_port=50056,
        db_name="documents",
        init_tables="documents,document_items",
    ),
    ServiceSpec(
        name="audit-service",
        service_dir=ROOT / "Services" / "audit-service",
        src_dir=ROOT / "Services" / "audit-service" / "src",
        module="audit_service.main",
        function="main_grpc",
        grpc_port=50057,
        db_name="audit",
        init_tables="audit_events",
        extra_env={"AUDIT_EVENT_CONSUMER_ENABLED": "0"},
    ),
    ServiceSpec(
        name="reporting-service",
        service_dir=ROOT / "Services" / "reporting-service",
        src_dir=ROOT / "Services" / "reporting-service" / "src",
        module="reporting_service.main",
        function="main_grpc",
        grpc_port=50058,
        db_name="reporting",
        init_tables=(
            "reporting_read_model_events,inventory_summary,document_summary,"
            "sales_summary,warehouse_activity_summary"
        ),
        extra_env={"REPORTING_READ_MODEL_CONSUMER_ENABLED": "0"},
    ),
    ServiceSpec(
        name="ai-service",
        service_dir=ROOT / "Services" / "ai-service",
        src_dir=ROOT / "Services" / "ai-service" / "src",
        module="ai_service.main",
        function="main_grpc",
        grpc_port=50059,
        extra_env={
            "AI_REINDEX_CONSUMER_ENABLED": "0",
            "VECTOR_DB_PATH": "/tmp/wms-ai-vector-db",
            "DB_CONNECTION_STRING": "sqlite:////tmp/wms-ai.db",
        },
    ),
)


GATEWAY_DIR = ROOT / "Services" / "api-gateway"
GATEWAY_SRC = GATEWAY_DIR / "src"


def _truthy(value: str | None, *, default: bool = True) -> bool:
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _grpc_addr(port: int) -> str:
    return f"{LOCAL_GRPC_HOST}:{port}"


def _base_env() -> dict[str, str]:
    env = os.environ.copy()
    defaults = {
        "PYTHONUNBUFFERED": "1",
        "LOG_FORMAT": "json",
        "OTEL_TRACES_EXPORTER": "none",
        "EVENTS_ENABLED": "0",
        "EVENT_BUS_URL": "",
        "EVENT_STREAM": "wms.events",
        "LOCAL_DB_BOOTSTRAP_ENABLED": "1",
        "DEBUG": "false",
        "JWT_ALGORITHM": "HS256",
        "SECRET_KEY": "replace-with-render-secret",
        "GRPC_TLS_ENABLED": "0",
        "GRPC_CLIENT_TLS_ENABLED": "0",
        "GRPC_CLIENT_ROOT_CERT_FILE": "",
        "GRPC_CLIENT_CERT_FILE": "",
        "GRPC_CLIENT_KEY_FILE": "",
        "CORS_ORIGINS": "*",
        "CORS_ALLOW_CREDENTIALS": "0",
        "MAX_REQUEST_BODY_BYTES": "1048576",
        "RATE_LIMIT_RPS": "10",
        "GRPC_TIMEOUT_FAST": "5",
        "GRPC_TIMEOUT_DEFAULT": "10",
        "GRPC_TIMEOUT_SLOW": "30",
        "GRPC_TIMEOUT_AI": "180",
        "GRPC_RETRY_ATTEMPTS": "2",
        "GRPC_RETRY_BACKOFF_SECONDS": "0.05",
        "CIRCUIT_BREAKER_FAILURE_THRESHOLD": "5",
        "CIRCUIT_BREAKER_RECOVERY_SECONDS": "15",
        # ── Render free-plan memory tunables ──────────────────────────────────
        # Ask glibc to return freed memory to the OS more aggressively
        "MALLOC_TRIM_THRESHOLD_": "65536",
        # Use the system allocator instead of CPython's pymalloc; makes trim
        # effective and reduces steady-state RSS by 5-15 MB per process
        "PYTHONMALLOC": "malloc",
        # Cap gRPC thread-pool concurrency per server (default: unlimited)
        "GRPC_MAX_CONCURRENT_RPCS": "4",
    }
    for key, value in defaults.items():
        env.setdefault(key, value)

    grpc_env_names = {
        "identity-service": "IDENTITY_GRPC_ADDR",
        "customer-service": "CUSTOMER_GRPC_ADDR",
        "product-service": "PRODUCT_GRPC_ADDR",
        "warehouse-service": "WAREHOUSE_GRPC_ADDR",
        "inventory-service": "INVENTORY_GRPC_ADDR",
        "documents-service": "DOCUMENTS_GRPC_ADDR",
        "audit-service": "AUDIT_GRPC_ADDR",
        "reporting-service": "REPORTING_GRPC_ADDR",
        "ai-service": "AI_GRPC_ADDR",
    }
    for service in GRPC_SERVICES:
        env.setdefault(grpc_env_names[service.name], _grpc_addr(service.grpc_port))
    return env


def _pythonpath(*src_dirs: Path) -> str:
    return os.pathsep.join(str(path) for path in (*src_dirs, SHARED_SRC))


def _service_env(service: ServiceSpec) -> dict[str, str]:
    env = _base_env()
    env["PYTHONPATH"] = _pythonpath(service.src_dir)
    if service.db_name:
        fallback = f"sqlite:////tmp/wms-{service.db_name}.db"
        env["DATABASE_URL"] = env.get(service.database_env_var or "", env.get("DATABASE_URL", fallback))
    if service.init_tables:
        env["INIT_DB_TABLES"] = env.get(service.init_tables_env_var or "", service.init_tables)
    for key, value in service.extra_env.items():
        env.setdefault(key, value)
    return env


def _gateway_env(port: int) -> dict[str, str]:
    env = _base_env()
    env["PYTHONPATH"] = _pythonpath(GATEWAY_SRC)
    env["PORT"] = str(port)
    return env


def _start_process(name: str, command: list[str], *, cwd: Path, env: dict[str, str]) -> subprocess.Popen:
    print(f"Starting {name}: {' '.join(command)}", flush=True)
    return subprocess.Popen(
        command,
        cwd=str(cwd),
        env=env,
        start_new_session=os.name != "nt",
    )


def _terminate_process(name: str, process: subprocess.Popen, *, grace_seconds: float = 10.0) -> None:
    if process.poll() is not None:
        return
    print(f"Stopping {name}...", flush=True)
    try:
        if os.name == "nt":
            process.terminate()
        else:
            os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return

    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return
        time.sleep(0.1)

    print(f"Force stopping {name}...", flush=True)
    try:
        if os.name == "nt":
            process.kill()
        else:
            os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return


def _shutdown(processes: list[tuple[str, subprocess.Popen]]) -> None:
    for name, process in reversed(processes):
        _terminate_process(name, process)


def main() -> int:
    port = int(os.getenv("PORT", "8000"))
    processes: list[tuple[str, subprocess.Popen]] = []

    def handle_shutdown(signum: int, _frame) -> None:
        print(f"Received signal {signum}; shutting down services.", flush=True)
        _shutdown(processes)
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    enabled_services = [
        service
        for service in GRPC_SERVICES
        if _truthy(os.getenv(service.run_env_var), default=True)
    ]
    for service in enabled_services:
        command = [
            sys.executable,
            "-c",
            f"from {service.module} import {service.function}; {service.function}()",
        ]
        processes.append(
            (
                service.name,
                _start_process(service.name, command, cwd=service.service_dir, env=_service_env(service)),
            )
        )

    delay = float(os.getenv("RUN_ALL_GATEWAY_DELAY_SECONDS", "10"))
    if delay > 0:
        time.sleep(delay)

    if _truthy(os.getenv("RUN_API_GATEWAY"), default=True):
        command = [
            sys.executable,
            "-m",
            "uvicorn",
            "api_gateway.app:create_app",
            "--factory",
            "--host",
            "0.0.0.0",
            "--port",
            str(port),
            # Render free plan: a single worker avoids forking a second Python
            # process (~75 MB) while still serving the demo workload fine.
            "--workers",
            "1",
        ]
        processes.append(
            (
                "api-gateway",
                _start_process("api-gateway", command, cwd=GATEWAY_DIR, env=_gateway_env(port)),
            )
        )

    print(f"All enabled services started. API gateway is listening on port {port}.", flush=True)

    try:
        while True:
            for name, process in processes:
                return_code = process.poll()
                if return_code is not None:
                    print(f"{name} exited with code {return_code}; stopping remaining services.", flush=True)
                    _shutdown(processes)
                    return return_code if return_code else 1
            time.sleep(1)
    finally:
        _shutdown(processes)


if __name__ == "__main__":
    raise SystemExit(main())
