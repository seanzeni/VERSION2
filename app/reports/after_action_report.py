from __future__ import annotations

# Purpose:
#     Generate date-driven after-action movement verification reports.

from collections import defaultdict
from datetime import date
from datetime import datetime
from pathlib import Path

from app.core.models import Element
from app.core.models import MainframeLocationRecord
from app.reports.pdf_utils import build_table
from app.reports.pdf_utils import heading
from app.reports.pdf_utils import page_break
from app.reports.pdf_utils import spacer
from app.reports.pdf_utils import subheading
from app.reports.pdf_utils import write_pdf
from app.reports.report_schemas import AFTER_ACTION_COLUMNS
from app.reports.report_schemas import names
from app.reports.report_utils import export_csv
from app.reports.report_utils import export_xlsx


class AfterActionReport:
    FILE_STEM = "After_Action_Report"

    def generate(
        self,
        rows: list[list[object]],
        output_folder: Path,
    ) -> Path:
        output_path = output_folder / f"{self.FILE_STEM}.csv"
        export_csv(
            output_path=output_path,
            headers=names(AFTER_ACTION_COLUMNS),
            rows=rows,
        )
        return output_path

    def generate_xlsx(
        self,
        rows: list[list[object]],
        output_folder: Path,
    ) -> Path:
        output_path = output_folder / f"{self.FILE_STEM}.xlsx"
        sheets: dict[str, tuple[list[str], list[list[object]]]] = {
            "After Action": (
                names(AFTER_ACTION_COLUMNS),
                rows,
            )
        }

        for group_name, group_rows in self._group_rows(rows).items():
            sheets[group_name] = (
                names(AFTER_ACTION_COLUMNS),
                group_rows,
            )

        export_xlsx(
            output_path=output_path,
            sheets=sheets,
        )
        return output_path

    def generate_pdf(
        self,
        rows: list[list[object]],
        output_folder: Path,
        selected_date: date,
    ) -> Path:
        output_path = output_folder / f"{self.FILE_STEM}.pdf"
        story = [
            heading("After Action Report"),
            subheading(f"Move Date {selected_date.isoformat()}"),
            spacer(),
        ]

        grouped = self._group_rows(rows)
        if not grouped:
            story.append(
                build_table(
                    headers=names(AFTER_ACTION_COLUMNS),
                    rows=[["", "", selected_date.isoformat(), "", "", "", "", "", "", "No", "", "", "", "No matching executed bundles found."]],
                )
            )
            return write_pdf(output_path, story, use_landscape=True)

        first_group = True
        for group_name, group_rows in grouped.items():
            if not first_group:
                story.append(page_break())
            first_group = False
            story.append(subheading(group_name))
            story.append(spacer())
            story.append(
                build_table(
                    headers=names(AFTER_ACTION_COLUMNS),
                    rows=group_rows,
                )
            )

        return write_pdf(output_path, story, use_landscape=True)

    def _group_rows(
        self,
        rows: list[list[object]],
    ) -> dict[str, list[list[object]]]:
        groups: dict[str, list[list[object]]] = defaultdict(list)

        for row in rows:
            release = str(row[0])
            mode = str(row[1])
            project = str(row[3])
            groups[f"{release} {mode} {project}"].append(row)

        return dict(sorted(groups.items()))


def build_after_action_row(
    release: str,
    mode: str,
    move_date: date,
    element: Element,
    expected_env: str,
    expected_system: str,
    expected_subsystem: str,
    record: MainframeLocationRecord | None,
) -> list[object]:
    moved = record is not None
    return [
        release,
        mode,
        move_date.isoformat(),
        element.project,
        element.element,
        element.type,
        expected_env,
        expected_system,
        expected_subsystem,
        "Yes" if moved else "No",
        record.ndvr_package if record is not None else "",
        f"{record.ndvr_rc:05d}" if record is not None and record.ndvr_rc is not None else "",
        record.time_generated if record is not None else "",
        "" if moved else "No matching NDVR record was found for the selected move date.",
    ]


def parse_report_date(
    value: object,
) -> date | None:
    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    text = str(value or "").strip()
    if not text:
        return None

    for format_text in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text[:10], format_text).date()
        except ValueError:
            continue

    return None
