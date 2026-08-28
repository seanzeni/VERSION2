from __future__ import annotations

# Purpose:
#     Dump tblFIXP1 Access database rows as JSON for the 64-bit FIXP report.
#
# Used By:
#     scripts/fixp_daily_compare.py
#
# Responsibilities:
#     - Connect to a 32-bit Microsoft Access ODBC driver.
#     - Read tblFIXP1.
#     - Emit only the columns needed by the FIXP daily comparison report.
#
# Notes:
#     Keep this helper lightweight. It is intended to run under 32-bit Python
#     where only requirements-32bit.txt needs to be installed.

import argparse
import json
import re
from datetime import date
from datetime import datetime
from pathlib import Path

import pyodbc


TABLE_NAME = "tblFIXP1"


def dump_access_rows(
    database_path: Path,
) -> list[dict[str, str]]:
    query = f"SELECT * FROM [{TABLE_NAME}]"
    rows: list[dict[str, str]] = []

    with pyodbc.connect(connection_string(database_path)) as connection:
        cursor = connection.cursor()
        cursor.execute(query)
        column_names = [str(column[0]) for column in cursor.description]

        for row in cursor.fetchall():
            row_data = {
                normalize_column_name(column_name): value
                for column_name, value in zip(column_names, row, strict=False)
            }
            output_row = build_output_row(row_data)
            if output_row is not None:
                rows.append(output_row)

    return rows


def connection_string(
    database_path: Path,
) -> str:
    return f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={database_path};"


def build_output_row(
    row_data: dict[str, object],
) -> dict[str, str] | None:
    element = clean(row_data.get("element", "")).upper()
    type_ = clean(row_data.get("type", "")).upper()
    system = clean(row_data.get("system", "")).upper()
    subsystem = clean(
        row_data.get(
            "subsystem",
            row_data.get(
                "subsytem",
                "",
            ),
        )
    ).upper()

    if not all(
        (
            element,
            type_,
            system,
            subsystem,
        )
    ):
        return None

    return {
        "element": element,
        "type": type_,
        "system": system,
        "subsystem": subsystem,
        "issues_fixes": clean(row_data.get("issuesfixes", "")),
        "comments": clean(row_data.get("comments", "")),
        "effort_id": clean(row_data.get("effortid", "")),
        "owner": clean(row_data.get("owner", "")),
        "manager": clean(row_data.get("manager", "")),
        "prod_date": clean(row_data.get("proddate", "")),
    }


def normalize_column_name(
    value: str,
) -> str:
    return re.sub(
        r"[^a-z0-9]",
        "",
        str(value).strip().lower(),
    )


def clean(
    value: object,
) -> str:
    if value is None:
        return ""

    if isinstance(value, (date, datetime)):
        return value.strftime("%Y-%m-%d")

    return str(value).strip()


def parse_args(
    argv: list[str] | None = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Dump tblFIXP1 rows from an Access database as JSON."
    )
    parser.add_argument(
        "database",
        help="Path to the Access database containing tblFIXP1.",
    )
    return parser.parse_args(argv)


def main(
    argv: list[str] | None = None,
) -> int:
    args = parse_args(argv)
    database_path = Path(args.database)
    print(json.dumps(dump_access_rows(database_path)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
