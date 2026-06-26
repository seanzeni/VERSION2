from __future__ import annotations

"""
Purpose:
    Central registry for available reports.

Used By:
    ReportCenter
    MainWindow

Responsibilities:
    - Register all report generators.
    - Provide display names.
    - Create report instances.
    - Route report generation calls.
"""

import csv
from pathlib import Path
from tempfile import TemporaryDirectory

from app.reports.effort_summary_report import EffortSummaryReport
from app.reports.issues_report import IssuesReport
from app.reports.osg_cops_report import OsgCopsReport
from app.reports.report_utils import export_xlsx
from app.reports.report_utils import make_writable
from app.reports.release_estimate_report import ReleaseEstimateReport
from app.reports.release_inventory_report import ReleaseInventoryReport
from app.reports.resync_report import ResyncReport


class ReportRegistry:
    def __init__(
        self,
        stats_service,
        location_service_provider=None,
    ) -> None:
        self.location_service_provider = location_service_provider

        self._reports = {
            "Issues Report": lambda: IssuesReport(),
            "Effort Summary Report": lambda: EffortSummaryReport(stats_service),
            "Release Estimate Report": lambda: ReleaseEstimateReport(stats_service),
            "Release Inventory Report": lambda: ReleaseInventoryReport(),
            "OSG/COPS Report": lambda: OsgCopsReport(),
            "Resync Report": lambda: ResyncReport(),
        }

    def get_names(
        self,
    ) -> list[str]:
        return sorted(self._reports.keys())

    def create(
        self,
        name: str,
    ):
        if name not in self._reports:
            raise KeyError(f"Unknown report: {name}")

        return self._reports[name]()

    def generate(
        self,
        name: str,
        output_format: str,
        state,
        output_folder: Path,
        include_empty: bool,
    ) -> Path | None:
        report = self.create(name)

        is_pdf = output_format.lower() == "pdf"
        is_xlsx = output_format.lower() == "xlsx"

        if name == "Issues Report":
            if is_pdf:
                raise NotImplementedError(f"PDF output is not implemented for {name}.")

            if is_xlsx:
                return self._generate_xlsx_from_csv(
                    output_folder=output_folder,
                    output_name="Issues_Report.xlsx",
                    generate_csv=lambda temp_folder: report.generate(
                        elements=state.loaded_elements,
                        output_folder=temp_folder,
                        include_empty=include_empty,
                    ),
                )

            return report.generate(
                elements=state.loaded_elements,
                output_folder=output_folder,
                include_empty=include_empty,
            )

        if name == "Effort Summary Report":
            if is_pdf:
                return report.generate_pdf(
                    elements=state.loaded_elements,
                    output_folder=output_folder,
                    mode=state.mode,
                    thread_count=state.thread_count,
                    include_empty=include_empty,
                )

            if is_xlsx:
                return self._generate_xlsx_from_csv(
                    output_folder=output_folder,
                    output_name="Effort_Summary_Report.xlsx",
                    generate_csv=lambda temp_folder: report.generate(
                        elements=state.loaded_elements,
                        output_folder=temp_folder,
                        mode=state.mode,
                        thread_count=state.thread_count,
                        include_empty=include_empty,
                    ),
                )

            return report.generate(
                elements=state.loaded_elements,
                output_folder=output_folder,
                mode=state.mode,
                thread_count=state.thread_count,
                include_empty=include_empty,
            )

        if name == "Release Estimate Report":
            if is_pdf:
                return report.generate_pdf(
                    elements=state.loaded_elements,
                    effort_dates=state.effort_dates,
                    output_folder=output_folder,
                    mode=state.mode,
                    thread_count=state.thread_count,
                    include_empty=include_empty,
                )

            if is_xlsx:
                return self._generate_xlsx_from_csv(
                    output_folder=output_folder,
                    output_name="Release_Estimate_Report.xlsx",
                    generate_csv=lambda temp_folder: report.generate(
                        elements=state.loaded_elements,
                        effort_dates=state.effort_dates,
                        output_folder=temp_folder,
                        mode=state.mode,
                        thread_count=state.thread_count,
                        include_empty=include_empty,
                    ),
                )

            return report.generate(
                elements=state.loaded_elements,
                effort_dates=state.effort_dates,
                output_folder=output_folder,
                mode=state.mode,
                thread_count=state.thread_count,
                include_empty=include_empty,
            )

        if name == "Release Inventory Report":
            if is_pdf:
                return report.generate_pdf(
                    release=state.release,
                    mode=state.mode,
                    thread_count=state.thread_count,
                    elements=state.loaded_elements,
                    inventory_issues=state.inventory_issues,
                    release_efforts=state.release_efforts,
                    output_folder=output_folder,
                    include_empty=include_empty,
                )

            if is_xlsx:
                return self._generate_xlsx_from_csv(
                    output_folder=output_folder,
                    output_name="Release_Inventory_Report.xlsx",
                    generate_csv=lambda temp_folder: report.generate(
                        release=state.release,
                        mode=state.mode,
                        thread_count=state.thread_count,
                        elements=state.loaded_elements,
                        inventory_issues=state.inventory_issues,
                        release_efforts=state.release_efforts,
                        output_folder=temp_folder,
                        include_empty=include_empty,
                    ),
                )

            return report.generate(
                release=state.release,
                mode=state.mode,
                thread_count=state.thread_count,
                elements=state.loaded_elements,
                inventory_issues=state.inventory_issues,
                release_efforts=state.release_efforts,
                output_folder=output_folder,
                include_empty=include_empty,
            )

        if name == "OSG/COPS Report":
            if is_pdf:
                return report.generate_pdf(
                    elements=state.loaded_elements,
                    output_folder=output_folder,
                    mode=state.mode,
                    include_empty=include_empty,
                )

            if is_xlsx:
                return self._generate_xlsx_from_csv(
                    output_folder=output_folder,
                    output_name="OSG_COPS_Report.xlsx",
                    generate_csv=lambda temp_folder: report.generate(
                        elements=state.loaded_elements,
                        output_folder=temp_folder,
                        mode=state.mode,
                        include_empty=include_empty,
                    ),
                )

            return report.generate(
                elements=state.loaded_elements,
                output_folder=output_folder,
                mode=state.mode,
                include_empty=include_empty,
            )

        if name == "Resync Report":
            location_service = self.get_location_service()

            if is_pdf:
                return report.generate_pdf(
                    release=state.release,
                    elements=state.loaded_elements,
                    location_service=location_service,
                    output_folder=output_folder,
                    include_empty=include_empty,
                )

            if is_xlsx:
                return self._generate_xlsx_from_csv(
                    output_folder=output_folder,
                    output_name="Resync_Report.xlsx",
                    generate_csv=lambda temp_folder: report.generate(
                        release=state.release,
                        elements=state.loaded_elements,
                        location_service=location_service,
                        output_folder=temp_folder,
                        include_empty=include_empty,
                    ),
                )

            return report.generate(
                release=state.release,
                elements=state.loaded_elements,
                location_service=location_service,
                output_folder=output_folder,
                include_empty=include_empty,
            )

        raise KeyError(f"Unknown report: {name}")

    def get_location_service(
        self,
    ):
        if self.location_service_provider is None:
            return None

        return self.location_service_provider()

    def _generate_xlsx_from_csv(
        self,
        output_folder: Path,
        output_name: str,
        generate_csv,
    ) -> Path:
        output_path = output_folder / output_name

        with TemporaryDirectory() as temp_dir:
            temp_folder = Path(temp_dir)
            generate_csv(temp_folder)

            sheets: dict[str, tuple[list[str], list[list[object]]]] = {}
            for csv_path in sorted(temp_folder.glob("*.csv")):
                with csv_path.open(
                    "r",
                    encoding="utf-8",
                    newline="",
                ) as file:
                    reader = csv.reader(file)
                    headers = next(reader, [])
                    rows = [row for row in reader]

                sheets[csv_path.stem.replace("_", " ")] = (
                    headers,
                    rows,
                )
                make_writable(csv_path)

            export_xlsx(
                output_path=output_path,
                sheets=sheets,
            )

        return output_path
