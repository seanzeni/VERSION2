from __future__ import annotations

# Purpose:
#     Generate a movement report for elements found in a configured reference list.

from pathlib import Path

from app.core.models import Element
from app.reports.pdf_utils import build_table
from app.reports.pdf_utils import heading
from app.reports.pdf_utils import spacer
from app.reports.pdf_utils import write_pdf
from app.reports.report_schemas import HIPPA_LISTENER_COLUMNS
from app.reports.report_schemas import names
from app.reports.report_schemas import ODS_ELEMENTS_COLUMNS
from app.reports.report_utils import export_csv
from app.reports.report_utils import export_xlsx
from app.services.reference_element_service import ReferenceElementService


class ReferenceMatchReport:
    def __init__(
        self,
        title: str,
        file_stem: str,
        list_name: str,
        reference_service: ReferenceElementService,
        include_listener_details: bool = False,
    ) -> None:
        self.title = title
        self.file_stem = file_stem
        self.list_name = list_name
        self.reference_service = reference_service
        self.include_listener_details = include_listener_details

    def generate(
        self,
        elements: list[Element],
        output_folder: Path,
        include_empty: bool = False,
    ) -> Path:
        output_path = output_folder / f"{self.file_stem}.csv"
        export_csv(
            output_path,
            self._headers(),
            self._build_rows(elements, include_empty),
        )
        return output_path

    def generate_xlsx(
        self,
        elements: list[Element],
        output_folder: Path,
        include_empty: bool = False,
    ) -> Path:
        output_path = output_folder / f"{self.file_stem}.xlsx"
        export_xlsx(
            output_path,
            {self.title[:31]: (
                self._headers(),
                self._build_rows(elements, include_empty),
            )},
        )
        return output_path

    def generate_pdf(
        self,
        elements: list[Element],
        output_folder: Path,
        include_empty: bool = False,
    ) -> Path:
        output_path = output_folder / f"{self.file_stem}.pdf"
        rows = self._build_rows(elements, include_empty)
        story = [
            heading(self.title),
            spacer(),
            build_table(
                headers=self._headers(),
                rows=rows or [self._empty_row()],
            ),
        ]
        return write_pdf(output_path, story, use_landscape=True)

    def _headers(
        self,
    ) -> list[str]:
        if self.include_listener_details:
            return names(HIPPA_LISTENER_COLUMNS)

        return names(ODS_ELEMENTS_COLUMNS)

    def _build_rows(
        self,
        elements: list[Element],
        include_empty: bool,
    ) -> list[list[str]]:
        matches = {
            element.key: (
                element,
                self.reference_service.get(
                    self.list_name,
                    element.element,
                    element.type,
                )
                or {},
            )
            for element in elements
            if element.visible
            and element.selected
            and self.reference_service.matches(
                self.list_name,
                element.element,
                element.type,
            )
        }
        rows = [
            self._row_for(
                element,
                reference_row,
            )
            for element, reference_row in sorted(
                matches.values(),
                key=lambda item: (
                    item[0].project.upper(),
                    item[0].element.upper(),
                    item[0].type.upper(),
                ),
            )
        ]
        if not rows and include_empty:
            return self._empty_row()
        return rows

    def _row_for(
        self,
        element: Element,
        reference_row: dict[str, str],
    ) -> list[str]:
        row = [
            element.release,
            element.project,
            element.element,
            element.type,
            str(element.source_row.get("Submitter", "")),
        ]

        if self.include_listener_details:
            row.extend(
                [
                    reference_row.get("Listener", ""),
                    reference_row.get("Listener Transactions", ""),
                ]
            )

        return row

    def _empty_row(
        self,
    ) -> list[str]:
        row = ["", "", "", "", "No matching moves found."]
        if self.include_listener_details:
            row.extend(["", ""])
        return row
