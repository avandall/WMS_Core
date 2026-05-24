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

    assert "archived reference code" in source
    assert "root `uv` workspace members" in source
    assert "Fixture Ownership" in source
    assert "identity-service" in source
    assert "Archived reference only" in readme


def test_roadmap_marks_phase_16_done_and_tracks_followups() -> None:
    source = (ROOT_DIR / "docs/roadmap.md").read_text()

    assert "Phase 16: Monolith Retirement & Codebase Simplification — DONE" in source
    assert "Phase 17: Production Deployment Automation — DONE" in source
    assert "Phase 18: Advanced Async/Analytics Workflows — DONE" in source
