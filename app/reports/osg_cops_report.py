from __future__ import annotations

# Purpose:
#     Generate the PROD-only OSG/COPS movement report.

from pathlib import Path

from app.core.models import Element
from app.core.package_rules import is_archive_package
from app.reports.pdf_utils import build_table
from app.reports.pdf_utils import heading
from app.reports.pdf_utils import spacer
from app.reports.pdf_utils import write_pdf
from app.reports.report_schemas import OSG_COPS_COLUMNS
from app.reports.report_schemas import names
from app.reports.report_utils import export_xlsx
from app.services.validation_rules.archive_rules import get_program_type_for_archive


class OsgCopsReport:
    XLSX_FILE_NAME = "OSG_COPS_Report.xlsx"
    PDF_FILE_NAME = "OSG_COPS_Report.pdf"

    def __init__(
        self,
        archive_pairs: list[list[str]] | None = None,
    ) -> None:
        self.archive_pairs = archive_pairs or []

    def generate_xlsx(
        self,
        elements: list[Element],
        output_folder: Path,
        mode: str,
        include_empty: bool = False,
    ) -> Path:
        report_path = output_folder / self.XLSX_FILE_NAME
        rows = self._build_rows(elements, mode, include_empty)
        export_xlsx(
            output_path=report_path,
            sheets={"OSG COPS": (names(OSG_COPS_COLUMNS), rows)},
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
            heading("OSG/COPS Report"),
            spacer(),
            build_table(
                headers=names(OSG_COPS_COLUMNS),
                rows=rows or [["", "", "", "", "", "No matching PROD moves found."]],
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
            return self._empty_rows(include_empty)

        moving = [
            element
            for element in elements
            if element.visible and element.selected and self._is_osg_cops_element(element)
        ]
        moving_keys = {element.key for element in moving}
        rows: list[list[str]] = []
        seen: set[tuple[str, str]] = set()

        for element in sorted(
            moving,
            key=lambda item: (
                item.element.upper(),
                item.type.upper(),
                item.project.upper(),
            ),
        ):
            if element.key in seen:
                continue

            if self._is_replaced_archive(element, moving_keys):
                continue

            seen.add(element.key)
            rows.append(
                [
                    element.release,
                    element.project,
                    element.element,
                    element.type,
                    str(element.source_row.get("Submitter", "")),
                    (
                        "Package archive"
                        if is_archive_package(element.source_row.get("Package", ""))
                        else ""
                    ),
                ]
            )

        return rows or self._empty_rows(include_empty)

    def _is_replaced_archive(
        self,
        element: Element,
        moving_keys: set[tuple[str, str]],
    ) -> bool:
        if not is_archive_package(element.source_row.get("Package", "")):
            return False

        program_type = get_program_type_for_archive(
            archive_type=element.type,
            archive_pairs=self.archive_pairs,
        )
        if program_type is None:
            return False

        return (element.element.strip().upper(), program_type) in moving_keys

    @staticmethod
    def _empty_rows(
        include_empty: bool,
    ) -> list[list[str]]:
        if not include_empty:
            return []
        return [["", "", "", "", "", "No matching PROD moves found."]]

    @staticmethod
    def _is_osg_cops_element(
        element: Element,
    ) -> bool:
        return element.element.upper().startswith(
            ("O", "X")
        ) or element.type.upper().startswith(("O", "X"))
