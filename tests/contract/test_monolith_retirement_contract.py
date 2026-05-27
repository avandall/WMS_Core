from __future__ import annotations

import tomllib
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]


def test_monolith_is_not_in_active_uv_workspace() -> None:
    pyproject = tomllib.loads((ROOT_DIR / "pyproject.toml").read_text())
    members = pyproject["tool"]["uv"]["workspace"]["members"]

    assert "Services/wms-monolith" not in members
    assert "Services/api-gateway" in members


def test_monolith_is_not_in_default_ci_or_proto_generation() -> None:
    ci_source = (ROOT_DIR / ".github/workflows/ci.yml").read_text()
    gen_source = (ROOT_DIR / "scripts/gen_protos.py").read_text()

    assert "Services/wms-monolith" not in ci_source
    assert "refactor_guard" not in ci_source
    assert "Services/wms-monolith" not in gen_source


def test_monolith_retirement_docs_define_archive_status_and_fixture_ownership() -> None:
    source = (ROOT_DIR / "docs/monolith_retirement.md").read_text()
    readme = (ROOT_DIR / "README.md").read_text()
    archive = (ROOT_DIR / "Services/wms-monolith/ARCHIVE.md").read_text()

    assert "archived reference code" in source
    assert "frozen read-only reference" in source
    assert "phase-o-monolith-archive-exit" in source
    assert "frozen read-only reference" in archive
    assert "Do not add new runtime features" in archive
    assert "root `uv` workspace members" in source
    assert "Fixture Ownership" in source
    assert "identity-service" in source
    assert "Archived reference only" in readme
    assert "phase-o-monolith-archive-exit" in readme


def test_active_runtime_paths_do_not_reference_monolith_archive() -> None:
    active_paths = [
        ROOT_DIR / ".github/workflows/ci.yml",
        ROOT_DIR / "docker-compose.yml",
        ROOT_DIR / "Dockerfile",
        ROOT_DIR / "scripts/gen_protos.py",
        ROOT_DIR / "scripts/bootstrap_e2e_identity.py",
        ROOT_DIR / "tests/e2e/run_gateway_stack_tests.sh",
    ]
    active_paths.extend((ROOT_DIR / "deploy/kubernetes").rglob("*"))

    checked_files = [
        path
        for path in active_paths
        if path.is_file() and path.suffix in {"", ".yml", ".yaml", ".py", ".sh", ".md"}
    ]

    for path in checked_files:
        source = path.read_text()
        assert "Services/wms-monolith" not in source, path
        assert "wms-monolith" not in source, path


def test_monolith_archive_readme_routes_contributors_to_services() -> None:
    source = (ROOT_DIR / "Services/wms-monolith/README.md").read_text()

    assert "frozen reference code" in source
    assert "not an active" in source
    assert "development, test, deployment, fixture, migration, or CI" in source
    assert "Services/api-gateway/" in source
    assert "Services/*-service/" in source
    assert "docker-compose.yml" in source
    assert "Historical Commands" in source


def test_roadmap_marks_phase_16_done_and_tracks_followups() -> None:
    source = (ROOT_DIR / "docs/roadmap.md").read_text()

    assert "Phase 16: Monolith Retirement & Codebase Simplification — DONE" in source
    assert "Phase 17: Production Deployment Automation — DONE" in source
    assert "Phase 18: Advanced Async/Analytics Workflows — DONE" in source
