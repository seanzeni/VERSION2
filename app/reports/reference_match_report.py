from __future__ import annotations

# Purpose:
#     Generate a movement report for elements found in a configured reference list.

from pathlib import Path

from app.core.models import Element
from app.reports.pdf_utils import build_table
from app.reports.pdf_utils import heading
from app.reports.pdf_utils import spacer
from app.reports.pdf_utils import write_pdf
from app.reports.report_schemas import MOVEMENT_MATCH_COLUMNS
from app.reports.report_schemas import names
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
    ) -> None:
        self.title = title
        self.file_stem = file_stem
        self.list_name = list_name
        self.reference_service = reference_service

    def generate(
        self,
        elements: list[Element],
        output_folder: Path,
        include_empty: bool = False,
    ) -> Path:
        output_path = output_folder / f"{self.file_stem}.csv"
        export_csv(
            output_path,
            names(MOVEMENT_MATCH_COLUMNS),
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
                names(MOVEMENT_MATCH_COLUMNS),
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
                headers=names(MOVEMENT_MATCH_COLUMNS),
                rows=rows or [["", "", "", "", "No matching moves found."]],
            ),
        ]
        return write_pdf(output_path, story, use_landscape=True)

    def _build_rows(
        self,
        elements: list[Element],
        include_empty: bool,
    ) -> list[list[str]]:
        matches = {
            element.key: element
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
            return [["", "", "", "", "No matching moves found."]]
        return rows

