from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any


REQUIRED_SERVICES = {
    "identity-service",
    "customer-service",
    "product-service",
    "warehouse-service",
    "inventory-service",
    "documents-service",
    "audit-service",
    "reporting-service",
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a production data cutover rehearsal manifest.")
    parser.add_argument("--manifest", required=True, help="Path to a cutover rehearsal manifest JSON file.")
    parser.add_argument("--dry-run", action="store_true", help="Validate the plan without opening databases.")
    return parser.parse_args()


def load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def validate_manifest(manifest: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    service_map = manifest.get("service_data_map", {})
    missing_services = REQUIRED_SERVICES - set(service_map)
    if missing_services:
        failures.append(f"missing service_data_map entries: {sorted(missing_services)}")

    rollback = manifest.get("rollback", {})
    for key in ("reference_tag", "database_snapshots", "event_offsets", "release_images"):
        if not rollback.get(key):
            failures.append(f"rollback.{key} is required")

    cutover = manifest.get("cutover", {})
    for key in ("order", "read_only_window", "post_cutover_checks"):
        if not cutover.get(key):
            failures.append(f"cutover.{key} is required")

    if "Services/wms-monolith" in json.dumps(manifest):
        failures.append("active cutover manifest must not use Services/wms-monolith as a runtime path")

    for group in ("count_checks", "orphan_checks", "total_checks", "freshness_checks"):
        for check in manifest.get(group, []):
            for key in ("name", "service", "target_db", "target_sql"):
                if key not in check:
                    failures.append(f"{group}.{check.get('name', '<unnamed>')} missing {key}")
            if group in {"count_checks", "total_checks"}:
                for key in ("source_db", "source_sql"):
                    if key not in check:
                        failures.append(f"{group}.{check.get('name', '<unnamed>')} missing {key}")

    return failures


def _sqlite_path(database_url: str) -> str:
    if not database_url.startswith("sqlite:///"):
        raise ValueError(f"only sqlite:/// rehearsal URLs are supported by this local checker: {database_url}")
    return database_url.removeprefix("sqlite:///")


def _scalar(databases: dict[str, str], db_name: str, sql: str) -> int | float:
    database_url = databases[db_name]
    with sqlite3.connect(_sqlite_path(database_url)) as connection:
        row = connection.execute(sql).fetchone()
    if row is None:
        raise ValueError(f"query returned no rows for {db_name}: {sql}")
    value = row[0]
    if not isinstance(value, int | float):
        raise ValueError(f"query must return a numeric scalar for {db_name}: {sql}")
    return value


def _within_tolerance(left: int | float, right: int | float, tolerance: int | float) -> bool:
    return abs(left - right) <= tolerance


def run_rehearsal(manifest: dict[str, Any], *, dry_run: bool) -> dict[str, Any]:
    failures = validate_manifest(manifest)
    result: dict[str, Any] = {
        "status": "failed" if failures else "passed",
        "dry_run": dry_run,
        "checked_services": sorted(manifest.get("service_data_map", {})),
        "checks": [],
        "failures": failures,
    }
    if failures or dry_run:
        if dry_run and not failures:
            result["status"] = "planned"
        return result

    databases = manifest.get("databases", {})

    for check in manifest.get("count_checks", []) + manifest.get("total_checks", []):
        source_value = _scalar(databases, check["source_db"], check["source_sql"])
        target_value = _scalar(databases, check["target_db"], check["target_sql"])
        tolerance = check.get("tolerance", 0)
        passed = _within_tolerance(source_value, target_value, tolerance)
        result["checks"].append(
            {
                "name": check["name"],
                "service": check["service"],
                "source": source_value,
                "target": target_value,
                "tolerance": tolerance,
                "passed": passed,
            }
        )
        if not passed:
            result["failures"].append(f"{check['name']} source={source_value} target={target_value}")

    for check in manifest.get("orphan_checks", []):
        value = _scalar(databases, check["target_db"], check["target_sql"])
        passed = value == 0
        result["checks"].append({"name": check["name"], "service": check["service"], "orphans": value, "passed": passed})
        if not passed:
            result["failures"].append(f"{check['name']} orphan_count={value}")

    for check in manifest.get("freshness_checks", []):
        value = _scalar(databases, check["target_db"], check["target_sql"])
        max_lag_seconds = check["max_lag_seconds"]
        passed = value <= max_lag_seconds
        result["checks"].append(
            {
                "name": check["name"],
                "service": check["service"],
                "lag_seconds": value,
                "max_lag_seconds": max_lag_seconds,
                "passed": passed,
            }
        )
        if not passed:
            result["failures"].append(f"{check['name']} lag_seconds={value}")

    result["status"] = "failed" if result["failures"] else "passed"
    return result


def main() -> None:
    args = _parse_args()
    manifest = load_manifest(Path(args.manifest))
    print(json.dumps(run_rehearsal(manifest, dry_run=args.dry_run), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
