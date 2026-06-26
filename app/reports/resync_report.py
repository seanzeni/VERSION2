from __future__ import annotations

"""
Purpose:
    Generate Resync Report CSV/PDF output.

Used By:
    ReportRegistry
    ReportCenter

Responsibilities:
    - Compare loaded inventory elements against NDVR location records.
    - Report lower-environment records when a higher environment has a newer
      version or a different CCID.
    - Exclude FIXP1 from resync comparisons.
"""

from pathlib import Path

from app.core.models import Element
from app.reports.pdf_utils import build_table
from app.reports.pdf_utils import heading
from app.reports.pdf_utils import spacer
from app.reports.pdf_utils import write_pdf
from app.reports.report_schemas import names
from app.reports.report_schemas import RESYNC_COLUMNS
from app.reports.report_utils import export_csv
from app.services.mainframe_location_service import MainframeLocationService


class ResyncReport:
    FILE_NAME = "Resync_Report.csv"
    PDF_FILE_NAME = "Resync_Report.pdf"

    def generate(
        self,
        release: str,
        elements: list[Element],
        location_service: MainframeLocationService | None,
        output_folder: Path,
        include_empty: bool = False,
    ) -> Path:
        report_path = output_folder / self.FILE_NAME

        rows = self.build_rows(
            release=release,
            elements=elements,
            location_service=location_service,
        )

        if not rows and not include_empty:
            rows = []

        export_csv(
            output_path=report_path,
            headers=names(RESYNC_COLUMNS),
            rows=rows,
        )

        return report_path

    def generate_pdf(
        self,
        release: str,
        elements: list[Element],
        location_service: MainframeLocationService | None,
        output_folder: Path,
        include_empty: bool = False,
    ) -> Path:
        report_path = output_folder / self.PDF_FILE_NAME
        rows = self.build_rows(
            release=release,
            elements=elements,
            location_service=location_service,
        )

        if not rows and not include_empty:
            rows = []

        story = [heading("Resync Report"), spacer()]
        story.append(
            build_table(
                headers=[
                    "Project",
                    "Element",
                    "Type",
                    "Lower",
                    "Higher",
                    "Reason",
                ],
                rows=[
                    [
                        row[1],
                        row[2],
                        row[3],
                        f"{row[4]} {row[7]} {row[8]}",
                        f"{row[9]} {row[12]} {row[13]}",
                        row[14],
                    ]
                    for row in rows
                ]
                or [["", "", "", "", "", "No potential resync issues found."]],
                column_widths=[
                    0.9 * 72,
                    0.9 * 72,
                    0.7 * 72,
                    1.5 * 72,
                    1.5 * 72,
                    4.3 * 72,
                ],
            )
        )

        return write_pdf(
            output_path=report_path,
            story=story,
            use_landscape=True,
        )

    def build_rows(
        self,
        release: str,
        elements: list[Element],
        location_service: MainframeLocationService | None,
    ) -> list[list[str]]:
        if location_service is None:
            return []

        rows: list[list[str]] = []
        seen_elements: set[tuple[str, str, str]] = set()

        for element in sorted(
            elements,
            key=lambda item: (
                item.project.upper(),
                item.element.upper(),
                item.type.upper(),
            ),
        ):
            element_key = (
                element.project.upper(),
                element.element.upper(),
                element.type.upper(),
            )

            if element_key in seen_elements:
                continue

            seen_elements.add(element_key)

            for detail in location_service.get_resync_details(
                element=element.element,
                type_=element.type,
            ):
                rows.append(
                    [
                        release,
                        element.project,
                        element.element,
                        element.type,
                        detail.get("lower_env", ""),
                        detail.get("lower_system", ""),
                        detail.get("lower_subsystem", ""),
                        detail.get("lower_version", ""),
                        detail.get("lower_ccid", ""),
                        detail.get("higher_env", ""),
                        detail.get("higher_system", ""),
                        detail.get("higher_subsystem", ""),
                        detail.get("higher_version", ""),
                        detail.get("higher_ccid", ""),
                        detail.get("reason", ""),
                    ]
                )

        return sorted(
            rows,
            key=lambda row: (
                row[1].upper(),
                row[2].upper(),
                row[3].upper(),
                row[4].upper(),
                row[9].upper(),
            ),
        )
