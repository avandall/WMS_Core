from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any


REQUIRED_DATASTORES = {
    "identity-service",
    "customer-service",
    "product-service",
    "warehouse-service",
    "inventory-service",
    "documents-service",
    "audit-service",
    "reporting-service",
}

REQUIRED_STREAMS = {
    "wms.events",
    "wms.events.replay",
    "wms.events.audit.dlq",
    "wms.events.inventory.dlq",
    "wms.events.reporting.dlq",
    "wms.events.ai.dlq",
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a backup/restore DR rehearsal manifest.")
    parser.add_argument("--manifest", required=True, help="Path to the DR rehearsal manifest JSON file.")
    parser.add_argument("--dry-run", action="store_true", help="Validate the manifest without opening databases.")
    return parser.parse_args()


def load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def validate_manifest(manifest: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    datastore_backups = manifest.get("datastore_backups", {})
    stream_backups = manifest.get("redis_stream_backups", {})
    missing_datastores = REQUIRED_DATASTORES - set(datastore_backups)
    missing_streams = REQUIRED_STREAMS - set(stream_backups)

    if missing_datastores:
        failures.append(f"missing datastore_backups entries: {sorted(missing_datastores)}")
    if missing_streams:
        failures.append(f"missing redis_stream_backups entries: {sorted(missing_streams)}")

    for service, backup in datastore_backups.items():
        for key in ("owner", "retention", "encrypted", "restore_order", "snapshot_id"):
            if key not in backup:
                failures.append(f"datastore_backups.{service}.{key} is required")
        if backup.get("encrypted") is not True:
            failures.append(f"datastore_backups.{service}.encrypted must be true")

    for stream, backup in stream_backups.items():
        for key in ("snapshot_id", "offset", "retention"):
            if key not in backup:
                failures.append(f"redis_stream_backups.{stream}.{key} is required")

    for key in ("rpo_rto", "restore_order", "validation_checks"):
        if not manifest.get(key):
            failures.append(f"{key} is required")

    required_workflows = {"auth", "document_posting", "inventory_reconcile", "reporting_rebuild"}
    missing_workflows = required_workflows - set(manifest.get("rpo_rto", {}))
    if missing_workflows:
        failures.append(f"missing rpo_rto workflows: {sorted(missing_workflows)}")

    for check in manifest.get("validation_checks", []):
        for key in ("name", "service", "target_db", "sql"):
            if key not in check:
                failures.append(f"validation_checks.{check.get('name', '<unnamed>')} missing {key}")

    return failures


def _sqlite_path(database_url: str) -> str:
    if not database_url.startswith("sqlite:///"):
        raise ValueError(f"only sqlite:/// rehearsal URLs are supported by this local checker: {database_url}")
    return database_url.removeprefix("sqlite:///")


def _scalar(databases: dict[str, str], db_name: str, sql: str) -> int | float:
    with sqlite3.connect(_sqlite_path(databases[db_name])) as connection:
        row = connection.execute(sql).fetchone()
    if row is None:
        raise ValueError(f"query returned no rows for {db_name}: {sql}")
    value = row[0]
    if not isinstance(value, int | float):
        raise ValueError(f"query must return a numeric scalar for {db_name}: {sql}")
    return value


def run_rehearsal(manifest: dict[str, Any], *, dry_run: bool) -> dict[str, Any]:
    failures = validate_manifest(manifest)
    result: dict[str, Any] = {
        "status": "failed" if failures else "passed",
        "dry_run": dry_run,
        "checked_datastores": sorted(manifest.get("datastore_backups", {})),
        "checked_streams": sorted(manifest.get("redis_stream_backups", {})),
        "checks": [],
        "failures": failures,
    }
    if failures or dry_run:
        if dry_run and not failures:
            result["status"] = "planned"
        return result

    databases = manifest.get("databases", {})
    for check in manifest.get("validation_checks", []):
        value = _scalar(databases, check["target_db"], check["sql"])
        expected = check.get("expected", 1)
        passed = value == expected
        result["checks"].append(
            {
                "name": check["name"],
                "service": check["service"],
                "value": value,
                "expected": expected,
                "passed": passed,
            }
        )
        if not passed:
            result["failures"].append(f"{check['name']} value={value} expected={expected}")

    result["status"] = "failed" if result["failures"] else "passed"
    return result


def main() -> None:
    args = _parse_args()
    manifest = load_manifest(Path(args.manifest))
    print(json.dumps(run_rehearsal(manifest, dry_run=args.dry_run), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
