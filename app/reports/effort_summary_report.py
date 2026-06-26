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

from app.core.models import ArchiveStatus
from app.core.models import Element
from app.core.models import FixStatus
from app.core.models import InventoryStatus
from app.core.models import LocationStatus
from app.core.models import MovementStatus
from app.core.models import ResyncStatus
from app.core.models import ScheduleStatus
from app.core.models import Severity
from app.reports.pdf_utils import build_table
from app.reports.pdf_utils import heading
from app.reports.pdf_utils import page_break
from app.reports.pdf_utils import spacer
from app.reports.pdf_utils import subheading
from app.reports.pdf_utils import write_pdf
from app.reports.report_schemas import EFFORT_SUMMARY_INVENTORY_COLUMNS
from app.reports.report_schemas import EFFORT_SUMMARY_SUMMARY_COLUMNS
from app.reports.report_schemas import names
from app.reports.report_utils import export_csv
from app.reports.report_utils import export_xlsx
from app.reports.status_glossary import get_report_glossary_rows


class EffortSummaryReport:
    FILE_NAME = "Effort_Summary_Report.csv"
    PDF_FILE_NAME = "Effort_Summary_Report.pdf"
    XLSX_FILE_NAME = "Effort_Summary_Report.xlsx"

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
        rows = self._build_inventory_rows(elements)

        export_csv(
            output_path=report_path,
            headers=names(EFFORT_SUMMARY_INVENTORY_COLUMNS),
            rows=rows,
        )

        return report_path

    def generate_xlsx(
        self,
        elements: list[Element],
        output_folder: Path,
        mode: str,
        thread_count: int,
        include_empty: bool = False,
    ) -> Path:
        report_path = output_folder / self.XLSX_FILE_NAME
        summary_headers = names(EFFORT_SUMMARY_SUMMARY_COLUMNS)
        inventory_headers = names(EFFORT_SUMMARY_INVENTORY_COLUMNS)
        glossary_headers = ["Section", "Field", "Value", "Severity", "Meaning"]

        export_xlsx(
            output_path=report_path,
            sheets={
                "Summary": (
                    summary_headers,
                    self._build_summary_rows(
                        elements=elements,
                        mode=mode,
                        thread_count=thread_count,
                        include_empty=include_empty,
                    ),
                ),
                "Inventory": (
                    inventory_headers,
                    self._build_inventory_rows(elements),
                ),
                "Information": (
                    glossary_headers,
                    get_report_glossary_rows(
                        EFFORT_SUMMARY_SUMMARY_COLUMNS
                        + EFFORT_SUMMARY_INVENTORY_COLUMNS
                    ),
                ),
            },
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

        summary_rows = self._build_pdf_summary_rows(
            grouped=grouped,
            mode=mode,
            thread_count=thread_count,
            include_empty=include_empty,
        )
        detail_projects = [
            project
            for project in sorted(grouped.keys())
            if grouped[project] or include_empty
        ]

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
            status_count_rows = self._build_status_count_rows(project_elements)
            story.append(
                build_table(
                    headers=["Status", "Count"],
                    rows=status_count_rows or [["No warning/error statuses", 0]],
                    column_widths=[2.8 * 72, 1.0 * 72],
                )
            )

        return write_pdf(report_path, story, use_landscape=True)

    def _build_summary_rows(
        self,
        elements: list[Element],
        mode: str,
        thread_count: int,
        include_empty: bool = False,
    ) -> list[list[object]]:
        grouped = self._group_elements(elements)
        rows: list[list[object]] = []

        for project in sorted(grouped.keys()):
            project_elements = grouped[project]

            if not project_elements and not include_empty:
                continue

            estimate = self.stats_service.build_estimate(
                elements=project_elements,
                mode=mode,
                thread_count=thread_count,
            )
            category_counts = estimate.get("category_counts", {})

            rows.append(
                [
                    project,
                    len([element for element in project_elements if element.selected]),
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

        return rows

    def _build_inventory_rows(
        self,
        elements: list[Element],
    ) -> list[list[object]]:
        return [
            [
                element.project,
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
            ]
            for element in sorted(
                elements,
                key=lambda item: (
                    item.project.upper(),
                    item.element.upper(),
                    item.type.upper(),
                ),
            )
        ]

    def _build_pdf_summary_rows(
        self,
        grouped: dict[str, list[Element]],
        mode: str,
        thread_count: int,
        include_empty: bool,
    ) -> list[list[object]]:
        rows: list[list[object]] = []

        for project in sorted(grouped.keys()):
            project_elements = grouped[project]

            if not project_elements and not include_empty:
                continue

            estimate = self.stats_service.build_estimate(
                elements=project_elements,
                mode=mode,
                thread_count=thread_count,
            )
            category_counts = estimate.get("category_counts", {})

            rows.append(
                [
                    project,
                    estimate.get("selected_elements", 0),
                    self._count_severity(project_elements, Severity.ERROR),
                    self._count_severity(project_elements, Severity.WARNING),
                    category_counts.get("COBOL", 0),
                    category_counts.get("APS", 0),
                    estimate.get("estimated_time", "00:00"),
                ]
            )

        return rows

    def _build_status_count_rows(
        self,
        elements: list[Element],
    ) -> list[list[object]]:
        counts: dict[str, int] = defaultdict(int)

        for element in elements:
            for label, value, severity in get_reportable_statuses(element):
                if value in {"OK", "FOUND"}:
                    continue

                if severity == Severity.INFO:
                    continue

                counts[label] += 1

        return [
            [
                label,
                counts[label],
            ]
            for label in sorted(counts.keys())
        ]

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


STATUS_LABELS = {
    InventoryStatus.OVERLAP.value: "Overlaps",
    InventoryStatus.DUPLICATE.value: "Duplicates",
    ScheduleStatus.INVENTORY_NOT_IN_RELEASE.value: "Inventory Not In Release",
    ScheduleStatus.INVENTORY_WHEN_SQL_NO_INVENTORY.value: "Unexpected Inventory",
    ScheduleStatus.SQL_EXPECTED_INVENTORY_MISSING.value: "Missing Inventory",
    ScheduleStatus.EFFORT_RELEASE_MISMATCH.value: "Wrong Release",
    LocationStatus.NOT_FOUND.value: "Not Found",
    ArchiveStatus.ARCHIVE_IN_QUAL.value: "Archive In QUAL",
    ArchiveStatus.POTENTIAL_MISSING_ARCHIVE.value: "Missing Archives",
    ArchiveStatus.POTENTIAL_MISSING_PROGRAM_MOVE.value: "Missing Programs",
    FixStatus.EXISTS_IN_FIXP1.value: "Exists In FIXP1",
    MovementStatus.DO_NOT_MOVE.value: "Do Not Move",
    MovementStatus.MARKED_IN_PROD.value: "Marked In PROD",
    MovementStatus.MARKED_IN_QUAL.value: "Marked In QUAL",
    MovementStatus.MARKED_ALREADY_THERE_BUT_MISSING.value: "Marked Missing From Environment",
    ResyncStatus.HIGHER_VERSION_EXISTS.value: "Potential Resync",
}


def get_reportable_statuses(
    element: Element,
) -> list[tuple[str, str, Severity]]:
    statuses = [
        element.inventory_status,
        element.schedule_status,
        element.location_status,
        element.archive_status,
        element.fix_status,
        element.movement_status,
        element.resync_status,
    ]

    return [
        (
            STATUS_LABELS.get(status.value, status.value.replace("_", " ").title()),
            status.value,
            status.severity,
        )
        for status in statuses
    ]
