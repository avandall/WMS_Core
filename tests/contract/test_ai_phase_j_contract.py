from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
AI_SERVICE_DIR = ROOT_DIR / "Services/ai-service/src/ai_service"


def _read(relative_path: str) -> str:
    return (ROOT_DIR / relative_path).read_text()


def _compose_config(*args: str) -> dict:
    result = subprocess.run(
        ["docker", "compose", *args, "config", "--format", "json"],
        cwd=ROOT_DIR,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_ai_remains_opt_in_for_default_compose() -> None:
    default_config = _compose_config()
    ai_config = _compose_config("--profile", "ai")

    assert "ai-service" not in default_config["services"]
    assert ai_config["services"]["ai-service"]["profiles"] == ["ai"]
    assert ai_config["services"]["ai-service"]["build"]["args"]["UV_PACKAGE"] == "ai-service"
    assert ai_config["services"]["ai-service"]["environment"]["AI_REINDEX_CONSUMER_ENABLED"] == "0"


def test_ai_pipeline_has_explicit_internal_stages() -> None:
    expected = {
        "ingestion.py",
        "indexing.py",
        "retrieval.py",
        "generation.py",
        "providers.py",
    }
    actual = {path.name for path in (AI_SERVICE_DIR / "pipeline").glob("*.py")}

    assert expected <= actual

    consumer = _read("Services/ai-service/src/ai_service/event_consumer.py")
    servicer = _read("Services/ai-service/src/ai_service/grpc_servicer.py")
    assert "EventIngestor" in consumer
    assert "JsonlReindexJobStore" in consumer
    assert "AIQueryPipeline" in servicer
    assert "WMSEngineProviderAdapter" in servicer

    package_init = _read("Services/ai-service/src/ai_service/__init__.py")
    assert "def __getattr__" in package_init
    assert "from .app import create_app" not in package_init


def test_ai_reindex_jobs_are_replayable_from_events_or_snapshots() -> None:
    ingestion = _read("Services/ai-service/src/ai_service/pipeline/ingestion.py")
    indexing = _read("Services/ai-service/src/ai_service/pipeline/indexing.py")

    assert "projection_snapshot" in ingestion
    assert "domain_event" in ingestion
    assert "replay_of_event_id" in ingestion
    assert "source_event_id" in ingestion
    assert "stream_id" in ingestion
    assert "class ReindexJobStore" in indexing
    assert "class JsonlReindexJobStore" in indexing


def test_ai_pipeline_does_not_read_operational_service_databases() -> None:
    forbidden = (
        "app.modules.",
        "Services/",
        "DATABASE_URL",
        "identity_service",
        "customer_service",
        "product_service",
        "warehouse_service",
        "inventory_service",
        "documents_service",
        "reporting_service",
    )
    checked_files = [
        AI_SERVICE_DIR / "event_consumer.py",
        *(AI_SERVICE_DIR / "pipeline").glob("*.py"),
    ]

    for path in checked_files:
        source = path.read_text()
        for text in forbidden:
            assert text not in source, f"{path.relative_to(ROOT_DIR)} references {text}"


def test_default_contract_and_e2e_tests_do_not_build_ai_profile() -> None:
    for test_dir in (ROOT_DIR / "tests/contract", ROOT_DIR / "tests/e2e"):
        for path in test_dir.glob("test_*.py"):
            if path.name == "test_ai_phase_j_contract.py":
                continue
            source = path.read_text()
            assert "--profile ai build ai-service" not in source
            assert "uv run --package ai-service" not in source
