from __future__ import annotations

from pathlib import Path

from app.core.models import ArchiveStatus
from app.core.models import Element
from app.reports.report_utils import archive_matching_reports
from app.reports.report_utils import archive_existing_reports
from app.reports.report_utils import build_report_file_prefix
from app.reports.report_utils import get_date_folder
from app.reports.report_utils import get_date_folder_path
from app.reports.report_utils import make_writable
from app.reports.report_utils import prefix_report_files
from app.reports.report_utils import safe_release_name
from app.reports.report_utils import sort_elements


def test_safe_release_name_replaces_unsafe_chars() -> None:
    """Verifies safe release name replaces unsafe chars."""
    assert safe_release_name("REL 2026/06") == "REL_2026_06"


def test_get_date_folder_creates_folder(tmp_path: Path) -> None:
    """Verifies get date folder creates folder."""
    folder = get_date_folder("REL1", tmp_path)
    assert folder.exists()
    assert folder.parent.name == "REL1"


def test_get_date_folder_path_does_not_create_folder(tmp_path: Path) -> None:
    """Verifies displaying the default report path has no filesystem side effect."""
    folder = get_date_folder_path("REL1", tmp_path)
    assert not folder.exists()
    assert folder.parent.name == "REL1"


def test_archive_existing_reports_moves_files(tmp_path: Path) -> None:
    """Verifies archive existing reports moves files."""
    report = tmp_path / "report.csv"
    report.write_text("data", encoding="utf-8")
    archive_existing_reports(tmp_path)
    assert not report.exists()
    assert (tmp_path / "History" / "report.csv").exists()
    make_writable(tmp_path / "History" / "report.csv")


def test_archive_existing_reports_keeps_existing_history_file(tmp_path: Path) -> None:
    """Verifies archive existing reports keeps existing history file."""
    history = tmp_path / "History"
    history.mkdir()
    existing = history / "report.csv"
    existing.write_text("old", encoding="utf-8")
    report = tmp_path / "report.csv"
    report.write_text("new", encoding="utf-8")

    archive_existing_reports(tmp_path)

    archived_files = sorted(history.glob("report*.csv"))
    assert len(archived_files) == 2
    assert existing.read_text(encoding="utf-8") == "old"
    for archived_file in archived_files:
        make_writable(archived_file)


def test_build_report_file_prefix_uses_release_and_move_date() -> None:
    """Verifies selected reports can be identified without their folder context."""
    assert (
        build_report_file_prefix("2026/07 Release", "2026-07-24")
        == "2026_07_RELEASE_2026-07-24"
    )


def test_archive_matching_reports_only_moves_same_release_date(tmp_path: Path) -> None:
    """Verifies history cleanup is scoped to the selected release and move date."""
    current = tmp_path / "2026_07_RELEASE_2026-07-24_Issues_Report.csv"
    other_date = tmp_path / "2026_07_RELEASE_2026-08-21_Issues_Report.csv"
    unprefixed = tmp_path / "Issues_Report.csv"
    current.write_text("current", encoding="utf-8")
    other_date.write_text("other", encoding="utf-8")
    unprefixed.write_text("new", encoding="utf-8")

    archive_matching_reports(
        tmp_path,
        "2026_07_RELEASE_2026-07-24",
    )

    assert not current.exists()
    assert (tmp_path / "History" / current.name).exists()
    assert other_date.exists()
    assert unprefixed.exists()
    make_writable(tmp_path / "History" / current.name)


def test_prefix_report_files_adds_release_and_move_date(tmp_path: Path) -> None:
    """Verifies generated files are renamed with the release/date context."""
    report = tmp_path / "Issues_Report.csv"
    report.write_text("data", encoding="utf-8")

    renamed = prefix_report_files(
        [report],
        "2026_07_RELEASE_2026-07-24",
    )

    assert renamed == [tmp_path / "2026_07_RELEASE_2026-07-24_Issues_Report.csv"]
    assert not report.exists()
    assert renamed[0].exists()
    make_writable(renamed[0])


def test_sort_elements_excludes_hidden_and_orders_errors_first() -> None:
    """Verifies sort elements excludes hidden and orders errors first."""
    error = Element(
        release="REL",
        project="ABC",
        element="ZZZ",
        type="OCOB",
        archive_status=ArchiveStatus.POTENTIAL_MISSING_ARCHIVE,
    )
    info = Element(release="REL", project="ABC", element="AAA", type="OCOB")
    hidden = Element(
        release="REL", project="ABC", element="BBB", type="OCOB", visible=False
    )
    assert sort_elements([info, hidden, error]) == [error, info]
