from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT = ROOT_DIR / "scripts/dr_rehearsal.py"
MANIFEST = ROOT_DIR / "deploy/kubernetes/examples/disaster-recovery-manifest.example.json"

_SPEC = importlib.util.spec_from_file_location("dr_rehearsal", SCRIPT)
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)


def test_phase_r_plan_is_marked_done() -> None:
    source = (ROOT_DIR / "docs/internal_architecture_refactor_plan.md").read_text()
    phase_r = source.split("## Phase R: Backup, Restore, and Disaster Recovery", 1)[1].split("## Phase S:", 1)[0]

    assert "Status: DONE." in phase_r
    assert "backup ownership, retention, encryption, and restore order" in phase_r
    assert "Redis Streams persistence, snapshot, and restore expectations" in phase_r
    assert "RPO/RTO targets" in phase_r


def test_dr_docs_cover_backup_stream_restore_and_validation() -> None:
    source = (ROOT_DIR / "docs/disaster_recovery.md").read_text()

    assert "Backup Ownership" in source
    assert "Redis Streams" in source
    assert "RPO/RTO Targets" in source
    assert "Restore Rehearsal" in source
    assert "scripts/dr_rehearsal.py" in source
    assert "auth works with restored users" in source
    assert "document posting is not duplicated" in source
    assert "inventory totals reconcile" in source
    assert "reporting projections can be rebuilt" in source


def test_dr_manifest_covers_datastores_streams_rpo_rto_and_checks() -> None:
    manifest = json.loads(MANIFEST.read_text())

    assert _MODULE.validate_manifest(manifest) == []
    assert set(manifest["datastore_backups"]) == _MODULE.REQUIRED_DATASTORES
    assert set(manifest["redis_stream_backups"]) == _MODULE.REQUIRED_STREAMS
    assert manifest["datastore_backups"]["identity-service"]["encrypted"] is True
    assert "document_posting" in manifest["rpo_rto"]
    assert "replay wms.events to the captured offset" in manifest["restore_order"]
    assert {check["name"] for check in manifest["validation_checks"]} >= {
        "auth users restored",
        "document posting idempotency ledger restored",
        "inventory totals reconcile",
        "reporting projection rebuilt",
    }


def test_dr_rehearsal_can_validate_disposable_sqlite_restore(tmp_path: Path) -> None:
    identity_db = tmp_path / "identity.db"
    documents_db = tmp_path / "documents.db"
    inventory_db = tmp_path / "inventory.db"
    reporting_db = tmp_path / "reporting.db"

    with sqlite3.connect(identity_db) as db:
        db.executescript("create table users(id integer primary key); insert into users values (1);")
    with sqlite3.connect(documents_db) as db:
        db.executescript("create table documents(id integer primary key, status text); insert into documents values (10, 'POSTED');")
    with sqlite3.connect(inventory_db) as db:
        db.executescript("create table inventory(id integer primary key, quantity integer); insert into inventory values (20, 7);")
    with sqlite3.connect(reporting_db) as db:
        db.executescript("create table reporting_read_model_events(id integer primary key); insert into reporting_read_model_events values (1);")

    manifest = json.loads(MANIFEST.read_text())
    manifest["databases"].update(
        {
            "identity": f"sqlite:///{identity_db}",
            "documents": f"sqlite:///{documents_db}",
            "inventory": f"sqlite:///{inventory_db}",
            "reporting": f"sqlite:///{reporting_db}",
        }
    )

    result = _MODULE.run_rehearsal(manifest, dry_run=False)

    assert result["status"] == "passed"
    assert result["failures"] == []
    assert len(result["checks"]) == 4
