from __future__ import annotations

from app.services.sharepoint_report_service import SharePointReportService


def test_sharepoint_url_converts_to_windows_webdav_path() -> None:
    """SharePoint links use the logged-on Windows WebDAV session."""
    path = SharePointReportService._to_webdav_path(
        "https://tenant.sharepoint.com/sites/Releases/Shared%20Documents/Reports"
    )

    assert str(path) == (
        "\\\\tenant.sharepoint.com@SSL\\DavWWWRoot\\sites\\Releases"
        "\\Shared Documents\\Reports"
    )

