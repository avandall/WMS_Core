from __future__ import annotations

import argparse
import os
from collections.abc import Iterable

from sqlalchemy import create_engine, inspect, text


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="List database tables and optional metadata.")
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL", ""),
        help="Database URL to inspect. Defaults to DATABASE_URL from the environment.",
    )
    parser.add_argument(
        "--show-columns",
        action="store_true",
        help="Print column metadata for each table.",
    )
    parser.add_argument(
        "--show-counts",
        action="store_true",
        help="Print row counts for each table.",
    )
    parser.add_argument(
        "--schema",
        default=None,
        help="Optional schema name to inspect.",
    )
    return parser.parse_args()


def _format_column(column: dict[str, object]) -> str:
    nullable = "null" if column.get("nullable") else "not null"
    column_type = column.get("type")
    return f"{column['name']} ({column_type}, {nullable})"


def _print_table_columns(inspector, table_name: str, schema: str | None) -> None:
    columns = inspector.get_columns(table_name, schema=schema)
    for column in columns:
        print(f"    - {_format_column(column)}")


def _print_row_count(engine, table_name: str, schema: str | None) -> None:
    qualified_name = f'"{table_name}"' if schema is None else f'"{schema}"."{table_name}"'
    with engine.connect() as connection:
        result = connection.execute(text(f"SELECT COUNT(*) FROM {qualified_name}"))
        count = result.scalar_one()
    print(f"    rows: {count}")


def _table_names(inspector, schema: str | None) -> Iterable[str]:
    return inspector.get_table_names(schema=schema)


def main() -> int:
    args = _parse_args()
    if not args.database_url:
        raise SystemExit("DATABASE_URL is required. Pass --database-url or export DATABASE_URL.")

    engine = create_engine(args.database_url)
    inspector = inspect(engine)
    tables = sorted(_table_names(inspector, args.schema))

    if not tables:
        print("No tables found.")
        return 0

    for table_name in tables:
        print(table_name)
        if args.show_columns:
            _print_table_columns(inspector, table_name, args.schema)
        if args.show_counts:
            _print_row_count(engine, table_name, args.schema)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


#python3 scripts/list_tables.py --database-url sqlite:////tmp/wms-identity.db --show-columns --show-counts
#python3 scripts/list_tables.py --show-columns