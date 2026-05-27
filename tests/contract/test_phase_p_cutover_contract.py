from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT_DIR / "scripts/cutover_rehearsal.py"
MANIFEST_PATH = ROOT_DIR / "deploy/kubernetes/examples/production-cutover-manifest.example.json"

_SPEC = importlib.util.spec_from_file_location("cutover_rehearsal", SCRIPT_PATH)
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)


def test_phase_p_plan_is_marked_done_and_lists_cutover_scope() -> None:
    source = (ROOT_DIR / "docs/internal_architecture_refactor_plan.md").read_text()

    phase_p = source.split("## Phase P: Production Data Cutover and Backfill", 1)[1].split("## Phase Q:", 1)[0]
    assert "Status: DONE." in phase_p
    assert "users/auth data to `identity-service`" in phase_p
    assert "reporting projections to `reporting-service` rebuild/backfill" in phase_p
    assert "Rollback steps identify the exact database snapshots" in phase_p


def test_cutover_docs_define_rehearsal_reconciliation_and_rollback() -> None:
    source = (ROOT_DIR / "docs/production_cutover.md").read_text()

    assert "Source To Target Map" in source
    assert "production-cutover-manifest.example.json" in source
    assert "scripts/cutover_rehearsal.py" in source
    assert "row counts" in source
    assert "orphan references" in source
    assert "document amount totals" in source
    assert "inventory quantity totals" in source
    assert "reporting projection freshness" in source
    assert "database snapshot identifiers" in source
    assert "Redis stream IDs" in source


def test_cutover_manifest_covers_services_checks_and_rollback() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text())
    failures = _MODULE.validate_manifest(manifest)

    assert failures == []
    assert set(manifest["service_data_map"]) == _MODULE.REQUIRED_SERVICES
    assert manifest["service_data_map"]["reporting-service"]["mode"] == "rebuild"
    assert "wms.events" in manifest["rollback"]["event_offsets"]
    assert "wms/api-gateway:RELEASE_VERSION" in manifest["rollback"]["release_images"]["api-gateway"]
    assert manifest["count_checks"]
    assert manifest["orphan_checks"]
    assert manifest["total_checks"]
    assert manifest["freshness_checks"]


def test_cutover_rehearsal_can_validate_disposable_sqlite_databases(tmp_path: Path) -> None:
    source_db = tmp_path / "source.db"
    identity_db = tmp_path / "identity.db"
    documents_db = tmp_path / "documents.db"
    inventory_db = tmp_path / "inventory.db"
    reporting_db = tmp_path / "reporting.db"

    with sqlite3.connect(source_db) as db:
        db.executescript(
            """
            create table users(id integer primary key);
            create table documents(id integer primary key, total_amount integer);
            create table inventory(id integer primary key, quantity integer);
            insert into users values (1);
            insert into documents values (10, 125);
            insert into inventory values (20, 7);
            """
        )
    with sqlite3.connect(identity_db) as db:
        db.executescript("create table users(id integer primary key); insert into users values (1);")
    with sqlite3.connect(documents_db) as db:
        db.executescript(
            """
            create table documents(id integer primary key, total_amount integer);
            create table document_items(id integer primary key, document_id integer);
            insert into documents values (10, 125);
            insert into document_items values (100, 10);
            """
        )
    with sqlite3.connect(inventory_db) as db:
        db.executescript("create table inventory(id integer primary key, quantity integer); insert into inventory values (20, 7);")
    with sqlite3.connect(reporting_db) as db:
        db.executescript("create table projection_status(lag_seconds integer); insert into projection_status values (0);")

    manifest = json.loads(MANIFEST_PATH.read_text())
    manifest["databases"].update(
        {
            "source": f"sqlite:///{source_db}",
            "identity": f"sqlite:///{identity_db}",
            "documents": f"sqlite:///{documents_db}",
            "inventory": f"sqlite:///{inventory_db}",
            "reporting": f"sqlite:///{reporting_db}",
        }
    )
    manifest["freshness_checks"][0]["target_sql"] = "select lag_seconds from projection_status"

    result = _MODULE.run_rehearsal(manifest, dry_run=False)

    assert result["status"] == "passed"
    assert result["failures"] == []
    assert {check["name"] for check in result["checks"]} >= {
        "users row count",
        "documents row count",
        "inventory quantity total",
        "document amount total",
        "reporting projection lag",
    }
