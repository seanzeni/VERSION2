from __future__ import annotations

# Purpose:
#     Generate the PROD-only PLANBIND movement report.

from pathlib import Path

from app.core.models import Element
from app.core.package_rules import is_archive_package
from app.reports.pdf_utils import build_table
from app.reports.pdf_utils import heading
from app.reports.pdf_utils import spacer
from app.reports.pdf_utils import write_pdf
from app.reports.report_schemas import MOVEMENT_MATCH_COLUMNS
from app.reports.report_schemas import names
from app.reports.report_utils import export_xlsx


class PlanbindReport:
    XLSX_FILE_NAME = "PLANBIND_Report.xlsx"
    PDF_FILE_NAME = "PLANBIND_Report.pdf"

    def generate_xlsx(
        self,
        elements: list[Element],
        output_folder: Path,
        mode: str,
        include_empty: bool = False,
    ) -> Path:
        report_path = output_folder / self.XLSX_FILE_NAME
        export_xlsx(
            output_path=report_path,
            sheets={
                "PLANBINDS": (
                    names(MOVEMENT_MATCH_COLUMNS),
                    self._build_rows(elements, mode, include_empty),
                )
            },
        )
        return report_path

    def generate_pdf(
        self,
        elements: list[Element],
        output_folder: Path,
        mode: str,
        include_empty: bool = False,
    ) -> Path:
        report_path = output_folder / self.PDF_FILE_NAME
        rows = self._build_rows(elements, mode, include_empty)
        story = [
            heading("PLANBIND Report"),
            spacer(),
            build_table(
                headers=names(MOVEMENT_MATCH_COLUMNS),
                rows=rows or [self._empty_row()],
            ),
        ]
        return write_pdf(report_path, story, use_landscape=True)

    def _build_rows(
        self,
        elements: list[Element],
        mode: str,
        include_empty: bool = False,
    ) -> list[list[str]]:
        if mode.upper() != "PROD":
            return [self._empty_row()] if include_empty else []

        matches = {
            element.key: element
            for element in elements
            if element.visible
            and element.selected
            and element.type.strip().upper() == "PLANBIND"
            and not is_archive_package(element.source_row.get("Package", ""))
        }
        rows = [
            [
                element.release,
                element.project,
                element.element,
                element.type,
                str(element.source_row.get("Submitter", "")),
            ]
            for element in sorted(
                matches.values(),
                key=lambda item: (
                    item.project.upper(),
                    item.element.upper(),
                    item.type.upper(),
                ),
            )
        ]

        if not rows and include_empty:
            return [self._empty_row()]
        return rows

    @staticmethod
    def _empty_row() -> list[str]:
        return ["", "", "", "", "No matching PROD PLANBIND moves found."]
