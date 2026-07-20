from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "fixp_daily_compare.py"
SPEC = importlib.util.spec_from_file_location("fixp_daily_compare", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
fixp_module = importlib.util.module_from_spec(SPEC)
sys.modules["fixp_daily_compare"] = fixp_module
SPEC.loader.exec_module(fixp_module)


def make_settings(
    tmp_path: Path,
    inventory_path: Path,
    fixp_folder: Path,
) -> dict:
    return {
        "files": {
            "default_fixp_folder": str(fixp_folder),
            "default_input_file": str(inventory_path),
            "default_output_folder": str(tmp_path / "output"),
        },
        "required_columns": [
            "Release",
            "DSN ID",
            "Project",
            "Element",
            "Type",
        ],
    }


def make_fixp_line(
    element: str,
    type_: str,
    system: str,
    subsystem: str,
    env: str,
    generated_date: str,
    version: str,
    user: str,
    ccid: str,
    comments: str = "COMMENTS",
) -> str:
    fields = [
        (element, 8),
        (type_, 8),
        (system, 8),
        (subsystem, 4),
        (env, 5),
        (generated_date, 10),
        ("12:00:00:00", 11),
        (version, 5),
        (user, 8),
        (ccid, 7),
        (comments, 40),
        ("00000", 5),
        ("", 1),
        ("PKG001", 16),
    ]
    return " ".join(value.ljust(width)[:width] for value, width in fields)


def write_inventory(
    tmp_path: Path,
) -> Path:
    """Creates inventory rows used to enrich FIXP comparison output."""
    path = tmp_path / "inventory.xlsx"
    pd.DataFrame(
        [
            {
                "Release": "2026/07 release",
                "DSN ID": "TL01OWNER",
                "Project": "ABC",
                "Element": "SAME001",
                "Type": "OCOB",
            },
            {
                "Release": "2026/08 release",
                "DSN ID": "TL02OWNER",
                "Project": "XYZ",
                "Element": "MOD001",
                "Type": "OCOB",
            },
            {
                "Release": "2026/09 release",
                "DSN ID": "TL03OWNER",
                "Project": "KEEP",
                "Element": "KEEP001",
                "Type": "OCOB",
            },
        ]
    ).to_excel(path, index=False)
    return path


def write_fixp_files(
    tmp_path: Path,
) -> Path:
    """Creates two-day FIXP snapshots where one row changes and one is deleted."""
    folder = tmp_path / "fixp"
    folder.mkdir()

    (folder / "FIXP-20260714_080000.txt").write_text(
        "\n".join(
            [
                make_fixp_line(
                    "SAME001",
                    "OCOB",
                    "SYSTEM01",
                    "SUB1",
                    "FIXP1",
                    "2026/07/14",
                    "01.01",
                    "USER01",
                    "CCID01",
                ),
                make_fixp_line(
                    "MOD001",
                    "OCOB",
                    "SYSTEM01",
                    "SUB1",
                    "FIXP1",
                    "2026/07/14",
                    "01.01",
                    "USER01",
                    "CCID01",
                ),
                make_fixp_line(
                    "KEEP001",
                    "OCOB",
                    "SYSTEM01",
                    "SUB1",
                    "FIXP1",
                    "2026/07/14",
                    "01.01",
                    "USER01",
                    "CCID01",
                ),
                make_fixp_line(
                    "DROP001",
                    "OCOB",
                    "SYSTEM01",
                    "SUB1",
                    "FIXP1",
                    "2026/07/14",
                    "01.01",
                    "USER01",
                    "CCID01",
                ),
            ]
        ),
        encoding="cp1252",
    )

    (folder / "FIXP-20260715_080000.txt").write_text(
        "\n".join(
            [
                make_fixp_line(
                    "SAME001",
                    "OCOB",
                    "SYSTEM01",
                    "SUB1",
                    "FIXP1",
                    "2026/07/15",
                    "01.01",
                    "USER01",
                    "CCID01",
                ),
                make_fixp_line(
                    "MOD001",
                    "OCOB",
                    "SYSTEM01",
                    "SUB1",
                    "FIXP1",
                    "2026/07/15",
                    "01.02",
                    "USER02",
                    "CCID02",
                ),
                make_fixp_line(
                    "KEEP001",
                    "OCOB",
                    "SYSTEM01",
                    "SUB1",
                    "FIXP1",
                    "2026/07/15",
                    "01.01",
                    "USER01",
                    "CCID01",
                ),
            ]
        ),
        encoding="cp1252",
    )

    (folder / "FIXP-20260715_100000.txt").write_text(
        make_fixp_line(
            "SAME001",
            "OCOB",
            "SYSTEM01",
            "SUB1",
            "FIXP1",
            "2026/07/15",
            "01.01",
            "USER01",
            "CCID99",
        ),
        encoding="cp1252",
    )

    return folder


def test_fixp_daily_compare_builds_expected_rows(
    tmp_path: Path,
) -> None:
    """Verifies day-over-day FIXP rows and inventory references."""
    inventory_path = write_inventory(tmp_path)
    fixp_folder = write_fixp_files(tmp_path)
    report = fixp_module.FixpDailyCompare(
        settings=make_settings(tmp_path, inventory_path, fixp_folder),
        base_dir=tmp_path,
    )

    rows = report.build_rows(date(2026, 7, 15))
    statuses = {row[4]: row[0] for row in rows}

    assert statuses == {
        "DROP001": "deleted",
        "KEEP001": "no change",
        "MOD001": "modified",
        "SAME001": "modified",
    }
    assert next(row[7] for row in rows if row[4] == "SAME001") == "CCID99"
    assert next(row[9] for row in rows if row[4] == "MOD001") == (
        "2026/08 release-XYZ-TL02"
    )
    assert next(row[6] for row in rows if row[4] == "DROP001") == "14-Jul-26"


def test_fixp_daily_compare_writes_xlsx(
    tmp_path: Path,
) -> None:
    """Verifies the standalone FIXP report writes one XLSX workbook."""
    inventory_path = write_inventory(tmp_path)
    fixp_folder = write_fixp_files(tmp_path)
    report = fixp_module.FixpDailyCompare(
        settings=make_settings(tmp_path, inventory_path, fixp_folder),
        base_dir=tmp_path,
    )

    output_files = report.run(date(2026, 7, 15))

    assert len(output_files) == 1
    assert output_files[0].suffix == ".xlsx"
    workbook = load_workbook(output_files[0], read_only=True)
    assert workbook.sheetnames == ["FIXP Compare"]
    workbook.close()


def test_fixp_daily_compare_defaults_to_latest_two_file_dates(
    tmp_path: Path,
) -> None:
    """Verifies default comparison uses the latest two FIXP file dates available."""
    inventory_path = write_inventory(tmp_path)
    fixp_folder = write_fixp_files(tmp_path)
    (fixp_folder / "FIXP-20260720_080000.txt").write_text(
        make_fixp_line(
            "KEEP001",
            "OCOB",
            "SYSTEM01",
            "SUB1",
            "FIXP1",
            "2026/07/20",
            "01.02",
            "USER01",
            "CCID20",
        ),
        encoding="cp1252",
    )
    report = fixp_module.FixpDailyCompare(
        settings=make_settings(tmp_path, inventory_path, fixp_folder),
        base_dir=tmp_path,
    )

    output_files = report.run(None)

    assert output_files[0].name == "FIXP_Daily_Compare_20260720.xlsx"
    rows = report.build_rows(None)
    statuses = {row[4]: row[0] for row in rows}
    assert statuses["KEEP001"] == "modified"
    assert statuses["SAME001"] == "deleted"


def test_parse_target_date_defaults_to_previous_day() -> None:
    """Verifies an explicit CLI date is parsed as the requested report date."""
    assert fixp_module.parse_target_date("2026-07-19", today=date(2026, 7, 20)) == date(
        2026,
        7,
        19,
    )


def test_parse_target_date_returns_none_for_default_file_window() -> None:
    """Verifies no CLI date allows the report to use latest available files."""
    assert fixp_module.parse_target_date(None, today=date(2026, 7, 20)) is None
