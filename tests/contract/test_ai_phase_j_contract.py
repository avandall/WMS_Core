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
        "backend_query.py",
        "ingestion.py",
        "indexing.py",
        "retrieval.py",
        "generation.py",
        "providers.py",
        "routing.py",
        "templates.py",
    }
    actual = {path.name for path in (AI_SERVICE_DIR / "pipeline").glob("*.py")}

    assert expected <= actual

    consumer = _read("Services/ai-service/src/ai_service/event_consumer.py")
    servicer = _read("Services/ai-service/src/ai_service/grpc_servicer.py")
    assert "EventIngestor" in consumer
    assert "JsonlReindexJobStore" in consumer
    assert "AIQueryPipeline" in servicer
    assert "WMSEngineProviderAdapter" in servicer

    generation = _read("Services/ai-service/src/ai_service/pipeline/generation.py")
    templates = _read("Services/ai-service/src/ai_service/pipeline/templates.py")
    backend_query = _read("Services/ai-service/src/ai_service/pipeline/backend_query.py")
    assert "router.route" in generation
    assert "template_extractor.extract" in generation
    assert "backend_query.execute" in generation
    assert "class GroqQueryTemplateExtractor" in templates
    assert "class QueryTemplateExtractor" in templates
    assert "class TemplateBackendQueryClient" in backend_query
    assert "class HttpBackendQueryClient" in backend_query
    assert "AI_BACKEND_QUERY_URL" in backend_query

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


def test_ai_query_pipeline_routes_data_questions_through_template_boundary() -> None:
    from ai_service.pipeline import AIQueryPipeline, QueryResult, QueryTemplate

    class Provider:
        calls = 0

        def generate(self, *, question: str, mode: str) -> QueryResult:
            self.calls += 1
            return QueryResult(success=True, mode=mode, response=f"rag:{question}")

        def status(self) -> dict[str, object]:
            return {}

    class Extractor:
        calls = 0

        def extract(self, *, question: str) -> QueryTemplate:
            self.calls += 1
            return QueryTemplate(
                intent="inventory_lookup",
                target="inventory",
                filters={"sku": "SKU-001"},
                metrics=("quantity",),
                raw_question=question,
            )

    class Backend:
        calls = 0
        last_template: QueryTemplate | None = None

        def execute(self, *, template: QueryTemplate):
            from ai_service.pipeline import BackendQueryResponse

            self.calls += 1
            self.last_template = template
            return BackendQueryResponse(success=True, payload={"rows": [{"quantity": 10}]})

    provider = Provider()
    extractor = Extractor()
    backend = Backend()
    pipeline = AIQueryPipeline(provider=provider, template_extractor=extractor, backend_query=backend)

    data_result = pipeline.answer(question="How many SKU-001 are in inventory?", mode="auto")
    knowledge_result = pipeline.answer(question="Explain warehouse slotting best practices", mode="auto")

    assert data_result.mode == "data_query"
    assert '"quantity": 10' in data_result.response
    assert extractor.calls == 1
    assert backend.calls == 1
    assert provider.calls == 1
    assert knowledge_result.mode == "rag"
    assert knowledge_result.response.startswith("rag:")


def test_default_contract_and_e2e_tests_do_not_build_ai_profile() -> None:
    for test_dir in (ROOT_DIR / "tests/contract", ROOT_DIR / "tests/e2e"):
        for path in test_dir.glob("test_*.py"):
            if path.name == "test_ai_phase_j_contract.py":
                continue
            source = path.read_text()
            assert "--profile ai build ai-service" not in source
            assert "uv run --package ai-service" not in source
