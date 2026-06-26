from __future__ import annotations

"""
Purpose:
    Generate Release Estimate Report CSV.

Used By:
    Reports dialog

Responsibilities:
    - Summarize selected visible elements by release move date.
    - Count selected elements by workload category.
    - Calculate estimated time by date.
    - Add a total row.

Notes:
    This report should not change selection state.
"""

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.models import Element
from app.reports.pdf_utils import build_table
from app.reports.pdf_utils import heading
from app.reports.pdf_utils import spacer
from app.reports.pdf_utils import write_pdf
from app.reports.report_schemas import RELEASE_ESTIMATE_COLUMNS
from app.reports.report_schemas import names
from app.reports.report_utils import export_csv


class ReleaseEstimateReport:
    FILE_NAME = "Release_Estimate_Report.csv"
    PDF_FILE_NAME = "Release_Estimate_Report.pdf"

    def __init__(
        self,
        stats_service: Any,
    ) -> None:
        self.stats_service = stats_service

    def generate(
        self,
        elements: list[Element],
        effort_dates: dict[str, str],
        output_folder: Path,
        mode: str,
        thread_count: int,
        include_empty: bool = False,
    ) -> Path:
        report_path = output_folder / self.FILE_NAME

        grouped: dict[str, list[Element]] = defaultdict(list)

        for element in elements:
            if not element.visible:
                continue

            if not element.selected:
                continue

            grouped[element.project].append(element)

        rows: list[list[str]] = []

        total_selected = 0
        total_minutes = 0
        total_category_counts: dict[str, int] = {}

        for effort in sorted(grouped.keys()):
            effort_elements = grouped[effort]

            if not effort_elements and not include_empty:
                continue

            estimate = self.stats_service.build_estimate(
                elements=effort_elements,
                mode=mode,
                thread_count=thread_count,
            )

            category_counts = estimate.get(
                "category_counts",
                {},
            )

            category_minutes = estimate.get(
                "category_minutes",
                {},
            )

            selected_count = int(
                estimate.get(
                    "selected_elements",
                    0,
                )
            )

            total_selected += selected_count
            total_minutes += int(
                estimate.get(
                    "total_minutes",
                    0,
                )
            )

            for category, count in category_counts.items():
                total_category_counts[category] = total_category_counts.get(
                    category,
                    0,
                ) + int(count)

            rows.append(
                [
                    effort,
                    effort_dates.get(
                        effort,
                        "Unknown",
                    ),
                    thread_count,
                    selected_count,
                    category_counts.get("JCL", 0),
                    category_counts.get("NON_COMPILE", 0),
                    category_counts.get("COBOL", 0),
                    category_counts.get("APS", 0),
                    category_counts.get("X_ELEMENTS", 0),
                    category_counts.get("LINKDECK", 0),
                    category_minutes.get("JCL", 0),
                    category_minutes.get("NON_COMPILE", 0),
                    category_minutes.get("COBOL", 0),
                    category_minutes.get("APS", 0),
                    category_minutes.get("X_ELEMENTS", 0),
                    category_minutes.get("LINKDECK", 0),
                    estimate.get("estimated_time", "00:00"),
                ]
            )

        if rows or include_empty:
            rows.append(
                [
                    "TOTAL",
                    "",
                    thread_count,
                    total_selected,
                    total_category_counts.get("JCL", 0),
                    total_category_counts.get("NON_COMPILE", 0),
                    total_category_counts.get("COBOL", 0),
                    total_category_counts.get("APS", 0),
                    total_category_counts.get("X_ELEMENTS", 0),
                    total_category_counts.get("LINKDECK", 0),
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    self.stats_service.format_minutes(total_minutes),
                ]
            )

        export_csv(
            output_path=report_path,
            headers=names(RELEASE_ESTIMATE_COLUMNS),
            rows=rows,
        )

        return report_path

    def generate_pdf(
        self,
        elements: list[Element],
        effort_dates: dict[str, str],
        output_folder: Path,
        release: str,
        mode: str,
        thread_count: int,
        include_empty: bool = False,
    ) -> Path:
        report_path = output_folder / self.PDF_FILE_NAME
        generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        selected_elements = [
            element
            for element in elements
            if element.visible and element.selected
        ]
        effort_count = len(
            {
                element.project
                for element in selected_elements
                if element.project
            }
        )
        estimate = self.stats_service.build_estimate(
            elements=selected_elements,
            mode=mode,
            thread_count=thread_count,
        )
        category_counts = estimate.get(
            "category_counts",
            {},
        )

        story = [
            heading("Release Estimate Report"),
            build_table(
                headers=[
                    "Generated",
                    "Bundle",
                    "Mode",
                    "Thread Count",
                ],
                rows=[[generated_at, release, mode, thread_count]],
            ),
            spacer(),
            build_table(
                headers=[
                    "Efforts",
                    "Selected",
                    "Estimate",
                ],
                rows=[
                    [
                        effort_count,
                        estimate.get("selected_elements", 0),
                        estimate.get("estimated_time", "00:00"),
                    ]
                ],
            ),
            spacer(),
            build_table(
                headers=[
                    "Category",
                    "Elements",
                ],
                rows=[
                    ["JCL", category_counts.get("JCL", 0)],
                    ["Non Compile", category_counts.get("NON_COMPILE", 0)],
                    ["COBOL", category_counts.get("COBOL", 0)],
                    ["APS", category_counts.get("APS", 0)],
                    ["X Elements", category_counts.get("X_ELEMENTS", 0)],
                    ["Linkdeck", category_counts.get("LINKDECK", 0)],
                ],
            ),
        ]

        return write_pdf(report_path, story, use_landscape=False)
