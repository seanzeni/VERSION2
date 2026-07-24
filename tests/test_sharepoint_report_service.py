from __future__ import annotations

from pathlib import Path

from app.services.sharepoint_report_service import SharePointReportService
from app.reports.report_utils import make_writable


def test_sharepoint_url_converts_to_windows_webdav_path() -> None:
    """SharePoint links use the logged-on Windows WebDAV session."""
    path = SharePointReportService._to_webdav_path(
        "https://tenant.sharepoint.com/sites/Releases/Shared%20Documents/Reports"
    )

    assert str(path) == (
        "\\\\tenant.sharepoint.com@SSL\\DavWWWRoot\\sites\\Releases"
        "\\Shared Documents\\Reports"
    )


def test_timestamp_files_can_include_move_date(tmp_path: Path) -> None:
    """Selected SharePoint reports include release and move date in the filename."""
    report = tmp_path / "Issues_Report.csv"
    report.write_text("data", encoding="utf-8")

    renamed = SharePointReportService.timestamp_files(
        [report],
        "2026/07 Release",
        move_date="2026-07-24",
    )

    assert len(renamed) == 1
    assert renamed[0].name.startswith("2026_07_RELEASE_2026-07-24_ISSUES_REPORT_")
    assert renamed[0].suffix == ".csv"
    make_writable(renamed[0])
