from __future__ import annotations

from datetime import date
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


def make_element(
    project: str = "ABC12345",
) -> Element:
    return Element(
        release="2026/07 release",
        project=project,
        element="PGM001",
        type="OCOB",
        source_row={
            "Act Rgn": "DV01",
            "Application": "APP1",
            "System": "PRIVATE0",
            "Subsys": "SYS1",
            "Submitter": "OWNER1",
        },
    )


def test_resync_qual_uses_selected_move_source_and_skips_moving_record(
    tmp_path: Path,
) -> None:
    """QUAL resync compares selected moving source to lower/equal envs."""
    service = location_service(
        tmp_path,
        [
            make_line("PGM001", "OCOB", "PRIVATE0", "SYS1", "STDV1", "02.00", "MOVE"),
            make_line("PGM001", "OCOB", "SHARED01", "SYS1", "UNIT1", "01.00", "UNIT"),
            make_line("PGM001", "OCOB", "SHARED01", "SYS1", "SYST1", "01.00", "ABC123"),
            make_line("PGM001", "OCOB", "PRIVATE0", "SYS1", "FIXP1", "99.99", "FIXP"),
        ],
    )

    rows = ResyncReport().build_rows(
        release="2026/07 release",
        mode="QUAL",
        elements=[make_element()],
        location_service=service,
        effort_dates={"ABC12345": "2026-07-24"},
        system_region_lookup={
            "SHARED01": "DV9",
        },
        effort_testing_region_lookup={
            "ABC12345": [
                (
                    "DV9",
                    date(2026, 7, 10),
                )
            ],
        },
    )

    assert len(rows) == 1
    assert rows[0][4:7] == ["APP1", "OWNER1", "2026-07-24"]
    assert rows[0][7:10] == ["SYST1", "DV9", "SHARED01"]
    assert rows[0][13] == "STDV1"
    assert rows[0][16] == "02.00"
    assert rows[0][18] == "plan to delete - moving to qual"


def test_resync_marks_lower_copy_for_retrofit_when_ccid_does_not_match(
    tmp_path: Path,
) -> None:
    """A lower system copy with a different CCID is treated as another effort."""
    service = location_service(
        tmp_path,
        [
            make_line("PGM001", "OCOB", "PRIVATE0", "SYS1", "STDV1", "02.00", "MOVE"),
            make_line(
                "PGM001", "OCOB", "SHARED01", "SYS1", "SYST1", "01.00", "FUTURE1"
            ),
        ],
    )
    moving_element = make_element()

    rows = ResyncReport().build_rows(
        release="2026/07 release",
        mode="QUAL",
        elements=[moving_element],
        location_service=service,
        effort_dates={
            "ABC12345": "2026-07-24",
        },
        system_region_lookup={
            "SHARED01": "DV8",
        },
    )

    assert len(rows) == 1
    assert rows[0][8] == "DV8"
    assert rows[0][18] == "plan for retrofit"


def test_resync_marks_matching_ccid_without_region_as_no_authorized_sandbox(
    tmp_path: Path,
) -> None:
    """A matching CCID in an unauthorized region should be planned for deletion."""
    service = location_service(
        tmp_path,
        [
            make_line("PGM001", "OCOB", "PRIVATE0", "SYS1", "STDV1", "02.00", "MOVE"),
            make_line("PGM001", "OCOB", "SHARED01", "SYS1", "SYST1", "01.00", "ABC123"),
        ],
    )

    rows = ResyncReport().build_rows(
        release="2026/07 release",
        mode="QUAL",
        elements=[make_element()],
        location_service=service,
        effort_dates={
            "ABC12345": "2026-07-24",
        },
        system_region_lookup={
            "SHARED01": "DV8",
        },
        effort_testing_region_lookup={
            "ABC12345": [
                (
                    "DV9",
                    date(2026, 7, 10),
                )
            ],
        },
    )

    assert len(rows) == 1
    assert rows[0][18] == "plan to delete - no authorized sandbox"


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
            make_line("PGM001", "OCOB", "SHARED01", "SYS1", "SYST1", "01.00", "SYST"),
            make_line("PGM001", "OCOB", "PRIVATE0", "SYS1", "UTDV1", "01.00", "UTDV"),
            make_line("PGM001", "OCOB", "PRIVATE1", "SYS1", "FIXP1", "99.99", "FIXP"),
        ],
    )

    rows = ResyncReport().build_rows(
        release="2026/07 release",
        mode="PROD",
        elements=[make_element()],
        location_service=service,
        system_region_lookup={
            "SHARED01": "DV9",
        },
    )

    assert [row[7] for row in rows] == ["SYST1"]
    assert rows[0][8] == "DV9"
    assert all(row[13] == "PROD1" for row in rows)
    assert all(row[16] == "03.00" for row in rows)
