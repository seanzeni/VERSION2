from __future__ import annotations

# Purpose:
#     Central registry for available reports.
#
# Used By:
#     ReportCenter
#     MainWindow
#
# Responsibilities:
#     - Register all report generators.
#     - Provide display names.
#     - Create report instances.
#     - Route report generation calls.

import csv
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from app.reports.effort_summary_report import EffortSummaryReport
from app.reports.issues_report import IssuesReport
from app.reports.osg_cops_report import OsgCopsReport
from app.reports.reference_match_report import ReferenceMatchReport
from app.reports.report_utils import export_xlsx
from app.reports.report_utils import make_writable
from app.reports.release_estimate_report import ReleaseEstimateReport
from app.reports.release_inventory_report import ReleaseInventoryReport
from app.reports.resync_report import ResyncReport
from app.services.reference_element_service import ReferenceElementService


ReportGenerator = Callable[[Any, Path, bool], Path | None]


@dataclass(frozen=True, slots=True)
class ReportDefinition:
    name: str
    xlsx_name: str
    csv_generator: ReportGenerator | None = None
    pdf_generator: ReportGenerator | None = None
    xlsx_generator: ReportGenerator | None = None


class ReportRegistry:
    def __init__(
        self,
        stats_service,
        location_service_provider=None,
        system_region_lookup_provider=None,
        archive_pairs: list[list[str]] | None = None,
        reference_element_service=None,
    ) -> None:
        self.stats_service = stats_service
        self.location_service_provider = location_service_provider
        self.system_region_lookup_provider = system_region_lookup_provider
        self.archive_pairs = archive_pairs or []
        self.reference_element_service = (
            reference_element_service or ReferenceElementService()
        )
        self._system_region_lookup: dict[str, str] | None = None

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
                    pdf_generator=self._generate_osg_cops_pdf,
                    xlsx_generator=self._generate_osg_cops_xlsx,
                ),
                ReportDefinition(
                    name="Resync Report",
                    xlsx_name="Resync_Report.xlsx",
                    csv_generator=self._generate_resync_csv,
                    pdf_generator=self._generate_resync_pdf,
                ),
                ReportDefinition(
                    name="HIPPA Listeners",
                    xlsx_name="HIPPA_Listeners.xlsx",
                    csv_generator=self._generate_hippa_csv,
                    pdf_generator=self._generate_hippa_pdf,
                    xlsx_generator=self._generate_hippa_xlsx,
                ),
                ReportDefinition(
                    name="ODS Elements",
                    xlsx_name="ODS_Elements.xlsx",
                    csv_generator=self._generate_ods_csv,
                    pdf_generator=self._generate_ods_pdf,
                    xlsx_generator=self._generate_ods_xlsx,
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

            if definition.csv_generator is None:
                raise NotImplementedError(f"XLSX output is not implemented for {name}.")

            return self._generate_xlsx_from_csv(
                output_folder=output_folder,
                output_name=definition.xlsx_name,
                generate_csv=lambda temp_folder: definition.csv_generator(
                    state,
                    temp_folder,
                    include_empty,
                ),
            )

        if definition.csv_generator is None:
            raise NotImplementedError(f"CSV output is not implemented for {name}.")

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

    def _generate_osg_cops_xlsx(
        self,
        state,
        output_folder: Path,
        include_empty: bool,
    ) -> Path:
        return OsgCopsReport(self.archive_pairs).generate_xlsx(
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
        return OsgCopsReport(self.archive_pairs).generate_pdf(
            elements=state.loaded_elements,
            output_folder=output_folder,
            mode=state.mode,
            include_empty=include_empty,
        )

    def _reference_report(
        self,
        title: str,
        file_stem: str,
        list_name: str,
    ) -> ReferenceMatchReport:
        return ReferenceMatchReport(
            title=title,
            file_stem=file_stem,
            list_name=list_name,
            reference_service=self.reference_element_service,
            include_listener_details=list_name == "hippa_listener",
        )

    def _generate_hippa_csv(
        self, state, output_folder: Path, include_empty: bool
    ) -> Path:
        return self._reference_report(
            "HIPPA Listeners", "HIPPA_Listeners", "hippa_listener"
        ).generate(state.loaded_elements, output_folder, include_empty)

    def _generate_hippa_xlsx(
        self, state, output_folder: Path, include_empty: bool
    ) -> Path:
        return self._reference_report(
            "HIPPA Listeners", "HIPPA_Listeners", "hippa_listener"
        ).generate_xlsx(state.loaded_elements, output_folder, include_empty)

    def _generate_hippa_pdf(
        self, state, output_folder: Path, include_empty: bool
    ) -> Path:
        return self._reference_report(
            "HIPPA Listeners", "HIPPA_Listeners", "hippa_listener"
        ).generate_pdf(state.loaded_elements, output_folder, include_empty)

    def _generate_ods_csv(
        self, state, output_folder: Path, include_empty: bool
    ) -> Path:
        return self._reference_report("ODS Elements", "ODS_Elements", "ods").generate(
            state.loaded_elements, output_folder, include_empty
        )

    def _generate_ods_xlsx(
        self, state, output_folder: Path, include_empty: bool
    ) -> Path:
        return self._reference_report(
            "ODS Elements", "ODS_Elements", "ods"
        ).generate_xlsx(state.loaded_elements, output_folder, include_empty)

    def _generate_ods_pdf(
        self, state, output_folder: Path, include_empty: bool
    ) -> Path:
        return self._reference_report(
            "ODS Elements", "ODS_Elements", "ods"
        ).generate_pdf(state.loaded_elements, output_folder, include_empty)

    def _generate_resync_csv(
        self,
        state,
        output_folder: Path,
        include_empty: bool,
    ) -> Path:
        return ResyncReport().generate(
            release=state.release,
            mode=state.mode,
            elements=state.loaded_elements,
            location_service=self.get_location_service(),
            output_folder=output_folder,
            effort_dates=state.effort_dates,
            tracked_elements=state.all_release_elements,
            system_region_lookup=self.get_system_region_lookup(),
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
            mode=state.mode,
            elements=state.loaded_elements,
            location_service=self.get_location_service(),
            output_folder=output_folder,
            effort_dates=state.effort_dates,
            tracked_elements=state.all_release_elements,
            system_region_lookup=self.get_system_region_lookup(),
            include_empty=include_empty,
        )

    def get_location_service(
        self,
    ):
        if self.location_service_provider is None:
            return None

        return self.location_service_provider()

    def get_system_region_lookup(
        self,
    ) -> dict[str, str]:
        if self.system_region_lookup_provider is None:
            return {}

        if self._system_region_lookup is None:
            self._system_region_lookup = self.system_region_lookup_provider()

        return self._system_region_lookup

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
