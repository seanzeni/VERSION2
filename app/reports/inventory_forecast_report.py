from __future__ import annotations

"""
Purpose:
    Generate one consolidated inventory-issues forecast report.

Used By:
    InventoryForecastService
    ReportCenter

Responsibilities:
    - Export consolidated inventory forecast rows to CSV, XLSX, and PDF.
    - Keep all qualifying releases in one report.
"""

from pathlib import Path

from app.reports.pdf_utils import build_table
from app.reports.pdf_utils import heading
from app.reports.pdf_utils import spacer
from app.reports.pdf_utils import write_pdf
from app.reports.report_schemas import INVENTORY_FORECAST_COLUMNS
from app.reports.report_schemas import names
from app.reports.report_utils import export_csv
from app.reports.report_utils import export_xlsx


class InventoryForecastReport:
    CSV_FILE_NAME = "Inventory_Issues_Forecast.csv"
    XLSX_FILE_NAME = "Inventory_Issues_Forecast.xlsx"
    PDF_FILE_NAME = "Inventory_Issues_Forecast.pdf"

    def generate(
        self,
        output_format: str,
        rows: list[list[object]],
        output_folder: Path,
    ) -> Path:
        clean_format = str(output_format).strip().lower()
        headers = names(INVENTORY_FORECAST_COLUMNS)

        if clean_format == "xlsx":
            output_path = output_folder / self.XLSX_FILE_NAME
            export_xlsx(
                output_path=output_path,
                sheets={"Inventory Issues": (headers, rows)},
            )
            return output_path

        if clean_format == "pdf":
            return self._generate_pdf(
                rows=rows,
                output_folder=output_folder,
            )

        output_path = output_folder / self.CSV_FILE_NAME
        export_csv(
            output_path=output_path,
            headers=headers,
            rows=rows,
        )
        return output_path

    def _generate_pdf(
        self,
        rows: list[list[object]],
        output_folder: Path,
    ) -> Path:
        output_path = output_folder / self.PDF_FILE_NAME
        pdf_rows = [
            [
                row[1],
                row[2],
                row[3],
                row[4],
                row[5],
                row[6],
                row[7],
                row[8],
                row[9],
            ]
            for row in rows
        ]
        story = [
            heading("Inventory Issues Forecast"),
            spacer(),
            build_table(
                headers=[
                    "Release",
                    "Next Move",
                    "Move Date",
                    "Project",
                    "Status",
                    "Count",
                    "Reason",
                    "Expected",
                    "Inventory",
                ],
                rows=pdf_rows
                or [
                    [
                        "",
                        "",
                        "",
                        "",
                        "No Issues",
                        0,
                        "No inventory issues found.",
                        "",
                        "",
                    ]
                ],
                column_widths=[
                    0.9 * 72,
                    0.55 * 72,
                    0.75 * 72,
                    0.7 * 72,
                    1.05 * 72,
                    0.45 * 72,
                    3.25 * 72,
                    0.9 * 72,
                    0.9 * 72,
                ],
            ),
        ]
        return write_pdf(
            output_path=output_path,
            story=story,
            use_landscape=True,
        )
