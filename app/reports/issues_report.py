from __future__ import annotations

# Purpose:
#     Generate Issues Report CSV.
#
# Used By:
#     Reports dialog
#
# Responsibilities:
#     - Export validation issues.
#     - Export warnings.

from pathlib import Path

from app.core.models import Element
from app.core.models import Severity
from app.reports.report_schemas import ISSUES_COLUMNS
from app.reports.report_schemas import ISSUES_GLOSSARY_COLUMNS
from app.reports.report_schemas import names
from app.reports.report_utils import export_csv
from app.reports.report_utils import sort_elements
from app.reports.status_glossary import get_issues_glossary_rows


class IssuesReport:
    FILE_NAME = "Issues_Report.csv"
    GLOSSARY_FILE_NAME = "Issues_Report_Status_Glossary.csv"

    def generate(
        self,
        elements: list[Element],
        output_folder: Path,
        include_empty: bool = False,
    ) -> Path:
        report_path = output_folder / self.FILE_NAME

        rows: list[list[str]] = []

        for element in sort_elements(elements):
            if not element.visible:
                continue

            if not include_empty and not element.display_reason:
                continue

            if element.severity not in {
                Severity.ERROR,
                Severity.WARNING,
            }:
                continue

            rows.append(
                [
                    element.element,
                    element.type,
                    element.project,
                    element.release,
                    element.expected_system,
                    element.expected_region,
                    element.severity.value,
                    element.inventory_status.value,
                    element.schedule_status.value,
                    element.location_status.value,
                    element.archive_status.value,
                    element.fix_status.value,
                    element.movement_status.value,
                    element.awareness_status.value,
                    element.packaging_status.value,
                    element.display_reason,
                ]
            )

        export_csv(
            output_path=report_path,
            headers=names(ISSUES_COLUMNS),
            rows=rows,
        )

        export_csv(
            output_path=output_folder / self.GLOSSARY_FILE_NAME,
            headers=names(ISSUES_GLOSSARY_COLUMNS),
            rows=get_issues_glossary_rows(),
        )

        return report_path
