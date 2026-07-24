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


def test_resync_qual_reports_system_copy_even_when_source_region_is_missing(
    tmp_path: Path,
) -> None:
    """QUAL resync reports found system copies without requiring source location."""
    service = location_service(
        tmp_path,
        [
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
            "SHARED01": "DVJ",
        },
        effort_testing_region_lookup={
            "ABC12345": [
                (
                    "DVF",
                    date(2026, 7, 10),
                )
            ],
        },
    )

    assert len(rows) == 1
    assert rows[0][4:7] == ["APP1", "OWNER1", "2026-07-24"]
    assert rows[0][7:10] == ["SYST1", "DVJ", "SHARED01"]
    assert rows[0][13] == "plan to delete - no authorized sandbox"
    assert "Found PGM001 OCOB in system region DVJ" in rows[0][14]


def test_resync_skips_records_in_authorized_testing_region(
    tmp_path: Path,
) -> None:
    """System copies in the release sandbox are expected to move and stay off report."""
    service = location_service(
        tmp_path,
        [
            make_line("PGM001", "OCOB", "SHARED01", "SYS1", "SYST1", "01.00", "ABC123"),
        ],
    )

    rows = ResyncReport().build_rows(
        release="2026/07 release",
        mode="QUAL",
        elements=[make_element()],
        location_service=service,
        effort_dates={"ABC12345": "2026-07-24"},
        system_region_lookup={
            "SHARED01": "DVF",
        },
        effort_testing_region_lookup={
            "ABC12345": [
                (
                    "DVF",
                    date(2026, 7, 10),
                )
            ],
        },
    )

    assert rows == []


def test_resync_includes_nonselectable_release_effort_elements(
    tmp_path: Path,
) -> None:
    """Validation-blocked elements still appear in release-specific resync."""
    service = location_service(
        tmp_path,
        [
            make_line("PGM001", "OCOB", "SHARED01", "SYS1", "SYST1", "01.00", "ABC123"),
        ],
    )
    element = make_element()
    element.selected = False
    element.selectable = False
    element.visible = False

    rows = ResyncReport().build_rows(
        release="2026/07 release",
        mode="QUAL",
        elements=[element],
        location_service=service,
        effort_dates={"ABC12345": "2026-07-24"},
        system_region_lookup={"SHARED01": "DVJ"},
        effort_testing_region_lookup={
            "ABC12345": [
                (
                    "DVF",
                    date(2026, 7, 10),
                )
            ],
        },
    )

    assert len(rows) == 1
    assert rows[0][2] == "PGM001"


def test_resync_marks_system_copy_for_retrofit_when_ccid_does_not_match(
    tmp_path: Path,
) -> None:
    """A system copy with a different CCID is treated as another effort."""
    service = location_service(
        tmp_path,
        [
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
    assert rows[0][13] == "plan for retrofit"


def test_resync_marks_matching_ccid_without_region_as_no_authorized_sandbox(
    tmp_path: Path,
) -> None:
    """A matching CCID in an unauthorized region should be planned for deletion."""
    service = location_service(
        tmp_path,
        [
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
    assert rows[0][13] == "plan to delete - no authorized sandbox"


def test_resync_reports_different_ccid_even_when_authorized_region_copy_exists(
    tmp_path: Path,
) -> None:
    """Different-CCID system copies are reported even when approved region exists."""
    service = location_service(
        tmp_path,
        [
            make_line("PGM001", "OCOB", "DVO0001", "SYS1", "SYST1", "01.00", "ABC123"),
            make_line("PGM001", "OCOB", "OTHER01", "SYS1", "STDV1", "01.00", "ZZZ999"),
            make_line("PGM001", "OCOB", "PRIVATE0", "SYS1", "UTDV1", "01.00", "UTDV"),
            make_line("PGM001", "OCOB", "PRIVATE1", "SYS1", "FIXP1", "99.99", "FIXP"),
        ],
    )

    rows = ResyncReport().build_rows(
        release="2026/07 release",
        mode="PROD",
        elements=[make_element()],
        location_service=service,
        effort_dates={"ABC12345": "2026-07-24"},
        system_region_lookup={
            "DVO0001": "DVO",
            "OTHER01": "DVX",
        },
        effort_testing_region_lookup={
            "ABC12345": [
                (
                    "DVO",
                    date(2026, 7, 10),
                )
            ],
        },
    )

    assert [row[8] for row in rows] == ["DVX"]
    assert [row[13] for row in rows] == [
        "plan for retrofit",
    ]
