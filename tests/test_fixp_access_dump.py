from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "fixp_access_dump.py"
SPEC = importlib.util.spec_from_file_location("fixp_access_dump", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
fixp_access_dump = importlib.util.module_from_spec(SPEC)
sys.modules["fixp_access_dump"] = fixp_access_dump
SPEC.loader.exec_module(fixp_access_dump)


def test_fixp_access_dump_reads_tbl_fixp1(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Verifies the 32-bit helper emits normalized tblFIXP1 rows."""
    database_path = tmp_path / "fixp.accdb"

    class Cursor:
        description = [
            ("Element",),
            ("Type",),
            ("System",),
            ("Subsytem",),
            ("Issues_Fixes",),
            ("Comments",),
            ("Effort_ID",),
            ("Owner",),
            ("Manager",),
            ("PROD_DATE",),
        ]

        def execute(
            self,
            query: str,
        ) -> None:
            assert query == "SELECT * FROM [tblFIXP1]"

        def fetchall(
            self,
        ):
            return [
                (
                    "mod001",
                    "ocob",
                    "system01",
                    "sub1",
                    "Issue text",
                    "Comment text",
                    "EFF123",
                    "Owner Name",
                    "Manager Name",
                    "2026-08-29",
                )
            ]

    class Connection:
        def __enter__(
            self,
        ):
            return self

        def __exit__(
            self,
            *args,
        ) -> None:
            return None

        def cursor(
            self,
        ) -> Cursor:
            return Cursor()

    monkeypatch.setattr(
        fixp_access_dump.pyodbc,
        "connect",
        lambda connection_string: Connection(),
    )

    rows = fixp_access_dump.dump_access_rows(database_path)

    assert rows == [
        {
            "element": "MOD001",
            "type": "OCOB",
            "system": "SYSTEM01",
            "subsystem": "SUB1",
            "issues_fixes": "Issue text",
            "comments": "Comment text",
            "effort_id": "EFF123",
            "owner": "Owner Name",
            "manager": "Manager Name",
            "prod_date": "2026-08-29",
        }
    ]
