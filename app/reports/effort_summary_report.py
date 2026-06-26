from __future__ import annotations

"""
Purpose:
    Generate Effort Summary Report CSV.

Used By:
    Reports dialog

Responsibilities:
    - Group inventory elements by effort/project.
    - Count selected elements.
    - Count errors, warnings, and info statuses.
    - Count selected elements by workload category.
    - Calculate estimated time per effort.
    - Include hidden inventory rows in detail output for auditability.
"""

from collections import defaultdict
from pathlib import Path
from typing import Any

from app.core.models import Element
from app.core.models import Severity
from app.reports.pdf_utils import build_table
from app.reports.pdf_utils import heading
from app.reports.pdf_utils import page_break
from app.reports.pdf_utils import spacer
from app.reports.pdf_utils import subheading
from app.reports.pdf_utils import write_pdf
from app.reports.report_schemas import EFFORT_SUMMARY_COLUMNS
from app.reports.report_schemas import names
from app.reports.report_utils import export_csv


class EffortSummaryReport:
    FILE_NAME = "Effort_Summary_Report.csv"
    PDF_FILE_NAME = "Effort_Summary_Report.pdf"

    def __init__(
        self,
        stats_service: Any,
    ) -> None:
        self.stats_service = stats_service

    def generate(
        self,
        elements: list[Element],
        output_folder: Path,
        mode: str,
        thread_count: int,
        include_empty: bool = False,
    ) -> Path:
        report_path = output_folder / self.FILE_NAME

        grouped: dict[str, list[Element]] = defaultdict(list)

        for element in elements:
            grouped[element.project].append(element)

        rows: list[list[object]] = []

        for project in sorted(grouped.keys()):
            project_elements = grouped[project]

            selected_elements = [
                element for element in project_elements if element.selected
            ]

            if not project_elements and not include_empty:
                continue

            estimate = self.stats_service.build_estimate(
                elements=project_elements,
                mode=mode,
                thread_count=thread_count,
            )

            category_counts = estimate.get(
                "category_counts",
                {},
            )

            rows.append(
                [
                    "Effort Summary",
                    project,
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    len(selected_elements),
                    self._count_severity(project_elements, Severity.ERROR),
                    self._count_severity(project_elements, Severity.WARNING),
                    self._count_severity(project_elements, Severity.INFO),
                    category_counts.get("JCL", 0),
                    category_counts.get("NON_COMPILE", 0),
                    category_counts.get("COBOL", 0),
                    category_counts.get("APS", 0),
                    category_counts.get("X_ELEMENTS", 0),
                    category_counts.get("LINKDECK", 0),
                    estimate.get("estimated_time", "00:00"),
                ]
            )

            for element in sorted(
                project_elements,
                key=lambda item: (
                    item.element.upper(),
                    item.type.upper(),
                ),
            ):
                rows.append(
                    [
                        "Inventory Detail",
                        project,
                        element.element,
                        element.type,
                        element.selected,
                        element.selectable,
                        element.visible,
                        element.severity.value,
                        element.inventory_status.value,
                        element.schedule_status.value,
                        element.location_status.value,
                        element.archive_status.value,
                        element.fix_status.value,
                        element.movement_status.value,
                        element.resync_status.value,
                        element.display_reason,
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                    ]
                )

        export_csv(
            output_path=report_path,
            headers=names(EFFORT_SUMMARY_COLUMNS),
            rows=rows,
        )

        return report_path

    def generate_pdf(
        self,
        elements: list[Element],
        output_folder: Path,
        mode: str,
        thread_count: int,
        include_empty: bool = False,
    ) -> Path:
        report_path = output_folder / self.PDF_FILE_NAME
        grouped = self._group_elements(elements)

        summary_rows: list[list[object]] = []
        detail_projects: list[str] = []

        for project in sorted(grouped.keys()):
            project_elements = grouped[project]
            selected_elements = [
                element for element in project_elements if element.selected
            ]

            if not project_elements and not include_empty:
                continue

            detail_projects.append(project)
            estimate = self.stats_service.build_estimate(
                elements=project_elements,
                mode=mode,
                thread_count=thread_count,
            )
            category_counts = estimate.get("category_counts", {})

            summary_rows.append(
                [
                    project,
                    len(selected_elements),
                    self._count_severity(project_elements, Severity.ERROR),
                    self._count_severity(project_elements, Severity.WARNING),
                    category_counts.get("COBOL", 0),
                    category_counts.get("APS", 0),
                    estimate.get("estimated_time", "00:00"),
                ]
            )

        story = [heading("Effort Summary Report"), spacer()]
        story.append(
            build_table(
                headers=[
                    "Project",
                    "Selected",
                    "Errors",
                    "Warnings",
                    "COBOL",
                    "APS",
                    "Estimate",
                ],
                rows=summary_rows or [["", 0, 0, 0, 0, 0, "00:00"]],
            )
        )

        for project in detail_projects:
            story.append(page_break())
            project_elements = grouped[project]
            estimate = self.stats_service.build_estimate(
                elements=project_elements,
                mode=mode,
                thread_count=thread_count,
            )
            story.append(subheading(f"Effort {project}"))
            story.append(
                build_table(
                    headers=["Selected", "Errors", "Warnings", "Estimate"],
                    rows=[
                        [
                            estimate.get("selected_elements", 0),
                            self._count_severity(project_elements, Severity.ERROR),
                            self._count_severity(project_elements, Severity.WARNING),
                            estimate.get("estimated_time", "00:00"),
                        ]
                    ],
                )
            )
            story.append(spacer())
            issue_rows = [
                [
                    element.element,
                    element.type,
                    element.severity.value,
                    element.display_reason,
                ]
                for element in project_elements
                if element.display_reason and element.severity != Severity.INFO
            ]
            story.append(
                build_table(
                    headers=["Element", "Type", "Severity", "Detail"],
                    rows=issue_rows or [["", "", "", "No issues found."]],
                    column_widths=[0.9 * 72, 0.7 * 72, 0.8 * 72, 7.0 * 72],
                )
            )

        return write_pdf(report_path, story, use_landscape=True)

    def _group_elements(
        self,
        elements: list[Element],
    ) -> dict[str, list[Element]]:
        grouped: dict[str, list[Element]] = defaultdict(list)

        for element in elements:
            grouped[element.project].append(element)

        return grouped

    def _count_severity(
        self,
        elements: list[Element],
        severity: Severity,
    ) -> int:
        return sum(
            1
            for element in elements
            if element.severity == severity
        )
