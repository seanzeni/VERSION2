from __future__ import annotations

"""
Purpose:
    Generate Release Inventory Report CSV.

Used By:
    Reports dialog

Responsibilities:
    - Report effort/project-level inventory issues.
    - Summarize missing inventory.
    - Summarize unexpected inventory for NOINV efforts.
    - Summarize inventory projects not connected to the SQL release.
    - Summarize inventory projects potentially tied to another SQL release.

Notes:
    This is an effort-level report.
    Individual element issues belong in IssuesReport.
"""

from collections import defaultdict
from datetime import datetime
from pathlib import Path

from app.core.models import Element
from app.core.models import InventoryIssue
from app.core.models import ReleaseEffort
from app.core.models import ScheduleStatus
from app.core.status_messages import StatusMessages
from app.reports.pdf_utils import build_table
from app.reports.pdf_utils import heading
from app.reports.pdf_utils import spacer
from app.reports.pdf_utils import write_pdf
from app.reports.report_schemas import RELEASE_INVENTORY_COLUMNS
from app.reports.report_schemas import names
from app.reports.report_utils import export_csv


class ReleaseInventoryReport:
    FILE_NAME = "Release_Inventory_Report.csv"
    PDF_FILE_NAME = "Release_Inventory_Report.pdf"

    def generate(
        self,
        release: str,
        mode: str,
        elements: list[Element],
        inventory_issues: list[InventoryIssue],
        release_efforts: list[ReleaseEffort],
        output_folder: Path,
        include_empty: bool = False,
    ) -> Path:
        report_path = output_folder / self.FILE_NAME
        generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rows = self._build_issue_rows(
            generated_at=generated_at,
            release=release,
            mode=mode,
            elements=elements,
            inventory_issues=inventory_issues,
            release_efforts=release_efforts,
            include_empty=include_empty,
        )

        export_csv(
            output_path=report_path,
            headers=names(RELEASE_INVENTORY_COLUMNS),
            rows=rows,
        )

        return report_path

    def generate_pdf(
        self,
        release: str,
        mode: str,
        elements: list[Element],
        inventory_issues: list[InventoryIssue],
        release_efforts: list[ReleaseEffort],
        output_folder: Path,
        include_empty: bool = False,
    ) -> Path:
        report_path = output_folder / self.PDF_FILE_NAME
        generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rows = self._build_issue_rows(
            generated_at=generated_at,
            release=release,
            mode=mode,
            elements=elements,
            inventory_issues=inventory_issues,
            release_efforts=release_efforts,
            include_empty=include_empty,
        )

        effort_dates = {
            effort.effort_id.strip(): (
                effort.prod_date if mode.upper() == "PROD" else effort.qual_date
            )
            for effort in release_efforts
            if effort.effort_id.strip()
        }

        pdf_rows = []
        for row in rows:
            project = row[3]
            move_date = effort_dates.get(project, "")
            if hasattr(move_date, "strftime"):
                move_date = move_date.strftime("%Y-%m-%d")
            pdf_rows.append(
                [
                    project,
                    str(move_date or ""),
                    row[4],
                    row[5],
                    row[6],
                    row[7],
                    row[8],
                ]
            )

        story = [
            heading("Release Inventory Report"),
            build_table(
                headers=["Release", "Mode", "Generated At"],
                rows=[[release, mode, generated_at]],
            ),
            spacer(),
            build_table(
                headers=[
                    "Project",
                    "Move Date",
                    "Inventory Status",
                    "Element Count",
                    "Reason",
                    "Expected Release",
                    "Inventory Release",
                ],
                rows=pdf_rows or [["", "", "No Issues", 0, "No release inventory issues found.", release, ""]],
                column_widths=[0.75 * 72, 0.75 * 72, 1.35 * 72, 0.7 * 72, 4.7 * 72, 0.95 * 72, 0.95 * 72],
            ),
        ]

        return write_pdf(report_path, story, use_landscape=True)

    def _build_issue_rows(
        self,
        generated_at: str,
        release: str,
        mode: str,
        elements: list[Element],
        inventory_issues: list[InventoryIssue],
        release_efforts: list[ReleaseEffort],
        include_empty: bool = False,
    ) -> list[list[str]]:
        rows: list[list[str]] = []

        elements_by_project = self._group_visible_elements_by_project(elements)

        efforts_by_id = {
            effort.effort_id.strip(): effort
            for effort in release_efforts
            if effort.effort_id.strip()
        }

        for issue in inventory_issues:
            if issue.issue_type != ScheduleStatus.SQL_EXPECTED_INVENTORY_MISSING:
                continue

            rows.append(
                [
                    generated_at,
                    release,
                    mode,
                    issue.effort_id,
                    "Missing Inventory",
                    0,
                    issue.reason,
                    issue.expected_release,
                    issue.inventory_release,
                ]
            )

        for project in sorted(elements_by_project.keys()):
            project_elements = elements_by_project.get(project, [])

            if not project_elements:
                continue

            first_element = project_elements[0]
            element_count = len(project_elements)
            effort = efforts_by_id.get(project)

            if effort is not None and (effort.no_inventory or effort.withdrawn):
                rows.append(
                    [
                        generated_at,
                        release,
                        mode,
                        project,
                        "Unexpected Inventory",
                        element_count,
                        (
                            "SQL marks this project as withdrawn, but inventory rows were found."
                            if effort.withdrawn
                            else "SQL marks this project as no inventory, but inventory rows were found."
                        ),
                        release,
                        first_element.release,
                    ]
                )
                continue

            inventory_not_in_release_element = get_project_element_with_schedule_status(
                project_elements,
                ScheduleStatus.INVENTORY_NOT_IN_RELEASE,
            )
            if inventory_not_in_release_element is not None:
                reason = get_inventory_reason(
                    inventory_not_in_release_element,
                    StatusMessages.INVENTORY_NOT_IN_RELEASE,
                )
                rows.append(
                    [
                        generated_at,
                        release,
                        mode,
                        project,
                        "Inventory Not In Release",
                        element_count,
                        reason,
                        release,
                        inventory_not_in_release_element.release,
                    ]
                )
                continue

            effort_release_mismatch_element = get_project_element_with_schedule_status(
                project_elements,
                ScheduleStatus.EFFORT_RELEASE_MISMATCH,
            )
            if effort_release_mismatch_element is not None:
                expected_release = get_expected_release(
                    effort_release_mismatch_element,
                    release,
                )
                reason = get_inventory_reason(
                    effort_release_mismatch_element,
                    StatusMessages.EFFORT_RELEASE_MISMATCH,
                )
                rows.append(
                    [
                        generated_at,
                        release,
                        mode,
                        project,
                        "Potential Wrong Release",
                        element_count,
                        reason,
                        expected_release,
                        effort_release_mismatch_element.release,
                    ]
                )

        if not rows and include_empty:
            rows.append(
                [
                    generated_at,
                    release,
                    mode,
                    "",
                    "No Issues",
                    0,
                    "No release inventory issues found.",
                    release,
                    "",
                ]
            )

        return rows

    def _group_visible_elements_by_project(
        self,
        elements: list[Element],
    ) -> dict[str, list[Element]]:
        grouped: dict[str, list[Element]] = defaultdict(list)

        for element in elements:
            if not element.visible:
                continue

            grouped[element.project].append(element)

        return dict(grouped)


def get_expected_release(
    element: Element,
    fallback_release: str,
) -> str:
    return str(
        element.source_row.get(
            "_sql_release",
            fallback_release,
        )
    )


def get_project_element_with_schedule_status(
    elements: list[Element],
    schedule_status: ScheduleStatus,
) -> Element | None:
    return next(
        (
            element
            for element in elements
            if element.schedule_status == schedule_status
        ),
        None,
    )


def get_inventory_reason(
    element: Element,
    message_prefix: str,
) -> str:
    for reason in element.reasons:
        if reason.startswith(message_prefix):
            return reason

    return message_prefix


