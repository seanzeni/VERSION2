from __future__ import annotations

from pathlib import Path

from app.core.models import Element
from app.reports.resync_report import ResyncReport
from app.services.mainframe_location_service import MainframeLocationService


def make_line(
    element: str,
    type_: str,
    system: str,
    subsystem: str,
    env: str,
    version: str,
    ccid: str,
) -> str:
    fields = [
        (element, 8),
        (type_, 8),
        (system, 8),
        (subsystem, 4),
        (env, 5),
        ("2026/07/16", 10),
        ("12:00:00:00", 11),
        (version, 5),
        ("USER01", 8),
        (ccid, 7),
        ("COMMENTS", 40),
        ("00000", 5),
        ("PKG001", 16),
    ]
    return " ".join(value.ljust(width)[:width] for value, width in fields)


def location_service(
    tmp_path: Path,
    lines: list[str],
) -> MainframeLocationService:
    path = tmp_path / "locations.txt"
    path.write_text(
        "\n".join(lines),
        encoding="cp1252",
    )
    return MainframeLocationService().load_file(path)


def make_element() -> Element:
    return Element(
        release="2026/07 release",
        project="ABC",
        element="PGM001",
        type="OCOB",
        source_row={
            "Act Rgn": "DV01",
            "System": "PRIVATE0",
            "Subsys": "SYS1",
        },
    )


def test_resync_qual_uses_qual_as_newer_source_and_skips_moving_record(
    tmp_path: Path,
) -> None:
    """QUAL resync compares QUAL to lower envs but skips the moving row."""
    service = location_service(
        tmp_path,
        [
            make_line("PGM001", "OCOB", "PRIVATE0", "SYS1", "QUAL1", "02.00", "QUAL"),
            make_line("PGM001", "OCOB", "PRIVATE0", "SYS1", "STDV1", "01.00", "MOVE"),
            make_line("PGM001", "OCOB", "SHARED01", "SYS1", "UNIT1", "01.00", "UNIT"),
            make_line("PGM001", "OCOB", "PRIVATE0", "SYS1", "FIXP1", "99.99", "FIXP"),
        ],
    )

    rows = ResyncReport().build_rows(
        release="2026/07 release",
        mode="QUAL",
        elements=[make_element()],
        location_service=service,
    )

    assert len(rows) == 1
    assert rows[0][4] == "UNIT1"
    assert rows[0][9] == "QUAL1"
    assert rows[0][12] == "02.00"


def test_resync_prod_uses_prod_as_newer_source_and_skips_moving_qual_record(
    tmp_path: Path,
) -> None:
    """PROD resync compares PROD to QUAL/unit/system but skips moving QUAL row."""
    service = location_service(
        tmp_path,
        [
            make_line("PGM001", "OCOB", "PRIVATE1", "SYS1", "PROD1", "03.00", "PROD"),
            make_line("PGM001", "OCOB", "PRIVATE1", "SYS1", "QUAL1", "02.00", "MOVE"),
            make_line("PGM001", "OCOB", "SHARED01", "SYS1", "QUAL1", "01.00", "QUAL"),
            make_line("PGM001", "OCOB", "PRIVATE0", "SYS1", "UTDV1", "01.00", "UTDV"),
            make_line("PGM001", "OCOB", "PRIVATE1", "SYS1", "FIXP1", "99.99", "FIXP"),
        ],
    )

    rows = ResyncReport().build_rows(
        release="2026/07 release",
        mode="PROD",
        elements=[make_element()],
        location_service=service,
    )

    assert [row[4] for row in rows] == ["QUAL1", "UTDV1"]
    assert all(row[9] == "PROD1" for row in rows)
    assert all(row[12] == "03.00" for row in rows)
