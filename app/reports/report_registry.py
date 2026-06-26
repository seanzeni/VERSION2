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
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from app.reports.effort_summary_report import EffortSummaryReport
from app.reports.issues_report import IssuesReport
from app.reports.osg_cops_report import OsgCopsReport
from app.reports.report_utils import export_xlsx
from app.reports.report_utils import make_writable
from app.reports.release_estimate_report import ReleaseEstimateReport
from app.reports.release_inventory_report import ReleaseInventoryReport
from app.reports.resync_report import ResyncReport


ReportGenerator = Callable[[Any, Path, bool], Path | None]


@dataclass(frozen=True, slots=True)
class ReportDefinition:
    name: str
    xlsx_name: str
    csv_generator: ReportGenerator
    pdf_generator: ReportGenerator | None = None
    xlsx_generator: ReportGenerator | None = None


class ReportRegistry:
    def __init__(
        self,
        stats_service,
        location_service_provider=None,
    ) -> None:
        self.stats_service = stats_service
        self.location_service_provider = location_service_provider

        self._reports = self._build_reports()

    def _build_reports(
        self,
    ) -> dict[str, ReportDefinition]:
        return {
            definition.name: definition
            for definition in [
                ReportDefinition(
                    name="Issues Report",
                    xlsx_name="Issues_Report.xlsx",
                    csv_generator=self._generate_issues_csv,
                ),
                ReportDefinition(
                    name="Effort Summary Report",
                    xlsx_name="Effort_Summary_Report.xlsx",
                    csv_generator=self._generate_effort_summary_csv,
                    pdf_generator=self._generate_effort_summary_pdf,
                    xlsx_generator=self._generate_effort_summary_xlsx,
                ),
                ReportDefinition(
                    name="Release Estimate Report",
                    xlsx_name="Release_Estimate_Report.xlsx",
                    csv_generator=self._generate_release_estimate_csv,
                    pdf_generator=self._generate_release_estimate_pdf,
                ),
                ReportDefinition(
                    name="Release Inventory Report",
                    xlsx_name="Release_Inventory_Report.xlsx",
                    csv_generator=self._generate_release_inventory_csv,
                    pdf_generator=self._generate_release_inventory_pdf,
                ),
                ReportDefinition(
                    name="OSG/COPS Report",
                    xlsx_name="OSG_COPS_Report.xlsx",
                    csv_generator=self._generate_osg_cops_csv,
                    pdf_generator=self._generate_osg_cops_pdf,
                ),
                ReportDefinition(
                    name="Resync Report",
                    xlsx_name="Resync_Report.xlsx",
                    csv_generator=self._generate_resync_csv,
                    pdf_generator=self._generate_resync_pdf,
                ),
            ]
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

        return self._reports[name]

    def generate(
        self,
        name: str,
        output_format: str,
        state,
        output_folder: Path,
        include_empty: bool,
    ) -> Path | None:
        definition = self.create(name)
        clean_format = output_format.lower()

        if clean_format == "pdf":
            if definition.pdf_generator is None:
                raise NotImplementedError(f"PDF output is not implemented for {name}.")

            return definition.pdf_generator(
                state,
                output_folder,
                include_empty,
            )

        if clean_format == "xlsx":
            if definition.xlsx_generator is not None:
                return definition.xlsx_generator(
                    state,
                    output_folder,
                    include_empty,
                )

            return self._generate_xlsx_from_csv(
                output_folder=output_folder,
                output_name=definition.xlsx_name,
                generate_csv=lambda temp_folder: definition.csv_generator(
                    state,
                    temp_folder,
                    include_empty,
                ),
            )

        return definition.csv_generator(
            state,
            output_folder,
            include_empty,
        )

    def _generate_issues_csv(
        self,
        state,
        output_folder: Path,
        include_empty: bool,
    ) -> Path:
        return IssuesReport().generate(
            elements=state.loaded_elements,
            output_folder=output_folder,
            include_empty=include_empty,
        )

    def _generate_effort_summary_csv(
        self,
        state,
        output_folder: Path,
        include_empty: bool,
    ) -> Path:
        return EffortSummaryReport(self.stats_service).generate(
            elements=state.loaded_elements,
            output_folder=output_folder,
            mode=state.mode,
            thread_count=state.thread_count,
            include_empty=include_empty,
        )

    def _generate_effort_summary_pdf(
        self,
        state,
        output_folder: Path,
        include_empty: bool,
    ) -> Path:
        return EffortSummaryReport(self.stats_service).generate_pdf(
            elements=state.loaded_elements,
            output_folder=output_folder,
            mode=state.mode,
            thread_count=state.thread_count,
            include_empty=include_empty,
        )

    def _generate_effort_summary_xlsx(
        self,
        state,
        output_folder: Path,
        include_empty: bool,
    ) -> Path:
        return EffortSummaryReport(self.stats_service).generate_xlsx(
            elements=state.loaded_elements,
            output_folder=output_folder,
            mode=state.mode,
            thread_count=state.thread_count,
            include_empty=include_empty,
        )

    def _generate_release_estimate_csv(
        self,
        state,
        output_folder: Path,
        include_empty: bool,
    ) -> Path:
        return ReleaseEstimateReport(self.stats_service).generate(
            elements=state.loaded_elements,
            effort_dates=state.effort_dates,
            output_folder=output_folder,
            mode=state.mode,
            thread_count=state.thread_count,
            include_empty=include_empty,
            count_all_movable_elements=getattr(
                state,
                "forecast_count_all_movable_elements",
                False,
            ),
        )

    def _generate_release_estimate_pdf(
        self,
        state,
        output_folder: Path,
        include_empty: bool,
    ) -> Path:
        return ReleaseEstimateReport(self.stats_service).generate_pdf(
            elements=state.loaded_elements,
            effort_dates=state.effort_dates,
            output_folder=output_folder,
            release=state.release,
            mode=state.mode,
            thread_count=state.thread_count,
            include_empty=include_empty,
            count_all_movable_elements=getattr(
                state,
                "forecast_count_all_movable_elements",
                False,
            ),
        )

    def _generate_release_inventory_csv(
        self,
        state,
        output_folder: Path,
        include_empty: bool,
    ) -> Path:
        return ReleaseInventoryReport().generate(
            release=state.release,
            mode=state.mode,
            elements=state.loaded_elements,
            inventory_issues=state.inventory_issues,
            release_efforts=state.release_efforts,
            output_folder=output_folder,
            include_empty=include_empty,
        )

    def _generate_release_inventory_pdf(
        self,
        state,
        output_folder: Path,
        include_empty: bool,
    ) -> Path:
        return ReleaseInventoryReport().generate_pdf(
            release=state.release,
            mode=state.mode,
            elements=state.loaded_elements,
            inventory_issues=state.inventory_issues,
            release_efforts=state.release_efforts,
            output_folder=output_folder,
            include_empty=include_empty,
        )

    def _generate_osg_cops_csv(
        self,
        state,
        output_folder: Path,
        include_empty: bool,
    ) -> Path:
        return OsgCopsReport().generate(
            elements=state.loaded_elements,
            output_folder=output_folder,
            mode=state.mode,
            include_empty=include_empty,
        )

    def _generate_osg_cops_pdf(
        self,
        state,
        output_folder: Path,
        include_empty: bool,
    ) -> Path:
        return OsgCopsReport().generate_pdf(
            elements=state.loaded_elements,
            output_folder=output_folder,
            mode=state.mode,
            include_empty=include_empty,
        )

    def _generate_resync_csv(
        self,
        state,
        output_folder: Path,
        include_empty: bool,
    ) -> Path:
        return ResyncReport().generate(
            release=state.release,
            elements=state.loaded_elements,
            location_service=self.get_location_service(),
            output_folder=output_folder,
            include_empty=include_empty,
        )

    def _generate_resync_pdf(
        self,
        state,
        output_folder: Path,
        include_empty: bool,
    ) -> Path:
        return ResyncReport().generate_pdf(
            release=state.release,
            elements=state.loaded_elements,
            location_service=self.get_location_service(),
            output_folder=output_folder,
            include_empty=include_empty,
        )

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
