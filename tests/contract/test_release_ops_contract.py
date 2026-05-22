from __future__ import annotations

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]


def test_release_ops_doc_covers_phase_15_contract() -> None:
    source = (ROOT_DIR / "docs/release_ops.md").read_text()

    required_sections = [
        "Release Identity",
        "Build And SBOM",
        "Deployment Contract",
        "Database Migrations",
        "Runbooks",
        "API And Proto Versioning",
    ]
    for section in required_sections:
        assert section in source

    assert "wms/api-gateway:$RELEASE_VERSION" in source
    assert "syft" in source
    assert "rollback gateway first" in source
    assert "REST remains under `/api/v1`" in source
    assert "Proto packages remain under `wms.<domain>.v1`" in source


def test_e2e_runner_prefers_uv_workspace() -> None:
    source = (ROOT_DIR / "tests/e2e/run_gateway_stack_tests.sh").read_text()

    assert source.index("command -v uv") < source.index('python3 -c "import httpx, pytest"')
    assert "uv run --group dev pytest -q tests/contract tests/e2e" in source


def test_stale_python_ci_workflow_was_removed() -> None:
    assert not (ROOT_DIR / ".github/workflows/python-ci.yml").exists()

    ci_source = (ROOT_DIR / ".github/workflows/ci.yml").read_text()
    assert "astral-sh/setup-uv" in ci_source
    assert "tests/e2e/run_gateway_stack_tests.sh" in ci_source
    assert "pip install pytest httpx" not in ci_source


def test_python_cache_artifacts_are_ignored() -> None:
    source = (ROOT_DIR / ".gitignore").read_text()

    assert "__pycache__/" in source
    assert "*.py[cod]" in source
    assert ".pytest_cache/" in source
