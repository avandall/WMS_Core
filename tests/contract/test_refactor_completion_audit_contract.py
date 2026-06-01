from __future__ import annotations

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (ROOT_DIR / relative_path).read_text()


def test_phase_k_audit_records_verification_and_rollback_points() -> None:
    audit = _read("docs/refactor_completion_audit.md")
    plan = _read("docs/internal_architecture_refactor_plan.md")

    assert "## Phase K: Refactor Completion Audit" in plan
    assert "Status: DONE." in plan
    assert "tests/e2e/run_gateway_stack_tests.sh" in audit
    assert "`78 passed`" in audit
    assert "docker compose config --quiet" in audit
    assert "docker compose --profile ai config --quiet" in audit
    assert "git diff --check" in audit

    for commit in (
        "16ac7ff",
        "31bfd15",
        "c8eafa5",
        "285f863",
        "1bb0cc7",
        "b1f2b9e",
        "cf4ca10",
        "b9fc678",
        "f1c99f0",
        "8edb8f3",
    ):
        assert commit in audit


def test_architecture_docs_do_not_keep_stale_completed_followups() -> None:
    data_ownership = _read("docs/data_ownership.md")
    plan = _read("docs/internal_architecture_refactor_plan.md")

    assert "Replace remaining reporting placeholders with projection tables and handlers in Phase F" not in data_ownership
    assert "Phase L: Production Migration and Fixture Ownership" in plan
    assert "Phase M: Transactional Event Delivery Hardening" in plan
    assert "Phase N: Deployment, Observability, and Security Hardening" in plan
    assert "Phase O: Monolith Archive Exit" in plan
