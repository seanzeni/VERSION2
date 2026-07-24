from __future__ import annotations

# Purpose:
#     Publish reports to SharePoint through the logged-on user's Windows WebDAV session.

from datetime import datetime
from pathlib import Path
from urllib.parse import unquote
from urllib.parse import urlparse

from app.reports.report_utils import archive_matching_reports
from app.reports.report_utils import archive_existing_reports
from app.reports.report_utils import build_report_file_prefix
from app.reports.report_utils import make_read_only
from app.reports.report_utils import safe_release_name


class SharePointReportService:
    def __init__(
        self,
        document_library_url: str,
    ) -> None:
        self.root = self._to_webdav_path(document_library_url)

    def get_release_folder(
        self,
        release: str,
    ) -> Path:
        folder = self.root / safe_release_name(release)
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def prepare_release_folder(
        self,
        release: str,
        file_prefix: str | None = None,
    ) -> Path:
        folder = self.get_release_folder(release)
        if file_prefix:
            archive_matching_reports(
                folder,
                file_prefix,
            )
        else:
            archive_existing_reports(folder)
        return folder

    @staticmethod
    def timestamp_files(
        files: list[Path],
        release: str,
        move_date: str | object | None = None,
    ) -> list[Path]:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        release_name = (
            build_report_file_prefix(
                release,
                move_date,
            )
            if move_date is not None
            else safe_release_name(release).upper()
        )
        renamed: list[Path] = []

        for path in files:
            if not path.exists():
                continue
            destination = path.with_name(
                f"{release_name}_{path.stem.upper()}_{timestamp}{path.suffix.lower()}"
            )
            path.replace(destination)
            make_read_only(destination)
            renamed.append(destination)

        return renamed

    @staticmethod
    def _to_webdav_path(url: str) -> Path:
        parsed = urlparse(str(url).strip())
        if parsed.scheme.lower() != "https" or not parsed.netloc:
            raise ValueError(
                "reports.sharepoint_url must be an HTTPS SharePoint document-library URL."
            )

        relative_path = unquote(parsed.path).replace("/", "\\").lstrip("\\")
        unc = f"\\\\{parsed.netloc}@SSL\\DavWWWRoot\\{relative_path}"
        return Path(unc)
