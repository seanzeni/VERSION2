from __future__ import annotations

# Purpose:
#     Generate Resync Report CSV/PDF output.
#
# Used By:
#     ReportRegistry
#     ReportCenter
#
# Responsibilities:
#     - Compare loaded inventory elements against NDVR location records.
#     - Report system-region records for release elements moving on the same date.
#     - Ignore UNIT/FIXP/QUAL/PROD records for this release-specific view.

from pathlib import Path

from app.core.models import Element
from app.core.models import MainframeLocationRecord
from app.core.release_rules import coerce_date
from app.reports.pdf_utils import build_table
from app.reports.pdf_utils import heading
from app.reports.pdf_utils import spacer
from app.reports.pdf_utils import write_pdf
from app.reports.report_schemas import names
from app.reports.report_schemas import RESYNC_COLUMNS
from app.reports.report_utils import export_csv
from app.services.mainframe_location_service import MainframeLocationService


class ResyncReport:
    FILE_NAME = "Resync_Report.csv"
    PDF_FILE_NAME = "Resync_Report.pdf"
    COMPARE_ENVS_BY_MODE = {
        "QUAL": {"SYST1", "STDV1"},
        "PROD": {"SYST1", "STDV1"},
    }
    SYSTEM_COMPARE_ENVS = {"SYST1", "STDV1"}

    def generate(
        self,
        release: str,
        mode: str,
        elements: list[Element],
        location_service: MainframeLocationService | None,
        output_folder: Path,
        effort_dates: dict[str, str] | None = None,
        tracked_elements: list[Element] | None = None,
        system_region_lookup: dict[str, str] | None = None,
        effort_testing_region_lookup: dict[str, list[tuple[str, object]]] | None = None,
        include_empty: bool = False,
    ) -> Path:
        report_path = output_folder / self.FILE_NAME

        rows = self.build_rows(
            release=release,
            mode=mode,
            elements=elements,
            location_service=location_service,
            effort_dates=effort_dates,
            tracked_elements=tracked_elements,
            system_region_lookup=system_region_lookup,
            effort_testing_region_lookup=effort_testing_region_lookup,
        )

        if not rows and not include_empty:
            rows = []

        export_csv(
            output_path=report_path,
            headers=names(RESYNC_COLUMNS),
            rows=rows,
        )

        return report_path

    def generate_pdf(
        self,
        release: str,
        mode: str,
        elements: list[Element],
        location_service: MainframeLocationService | None,
        output_folder: Path,
        effort_dates: dict[str, str] | None = None,
        tracked_elements: list[Element] | None = None,
        system_region_lookup: dict[str, str] | None = None,
        effort_testing_region_lookup: dict[str, list[tuple[str, object]]] | None = None,
        include_empty: bool = False,
    ) -> Path:
        report_path = output_folder / self.PDF_FILE_NAME
        rows = self.build_rows(
            release=release,
            mode=mode,
            elements=elements,
            location_service=location_service,
            effort_dates=effort_dates,
            tracked_elements=tracked_elements,
            system_region_lookup=system_region_lookup,
            effort_testing_region_lookup=effort_testing_region_lookup,
        )

        if not rows and not include_empty:
            rows = []

        story = [heading("Resync Report"), spacer()]
        story.append(
            build_table(
                headers=[
                    "Project",
                    "Application",
                    "Owner",
                    "QUAL Date",
                    "Element",
                    "Type",
                    "Testing Region",
                    "Location",
                    "Remarks",
                    "Reason",
                ],
                rows=[
                    [
                        row[1],
                        row[4],
                        row[5],
                        row[6],
                        row[2],
                        row[3],
                        row[8],
                        f"{row[7]} {row[11]} {row[12]}",
                        row[13],
                        row[14],
                    ]
                    for row in rows
                ]
                or [
                    [
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "No potential resync issues found.",
                    ]
                ],
                column_widths=[
                    0.9 * 72,
                    1.0 * 72,
                    0.8 * 72,
                    0.8 * 72,
                    0.9 * 72,
                    0.7 * 72,
                    1.0 * 72,
                    1.5 * 72,
                    1.2 * 72,
                    3.0 * 72,
                ],
            )
        )

        return write_pdf(
            output_path=report_path,
            story=story,
            use_landscape=True,
        )

    def build_rows(
        self,
        release: str,
        mode: str,
        elements: list[Element],
        location_service: MainframeLocationService | None,
        effort_dates: dict[str, str] | None = None,
        tracked_elements: list[Element] | None = None,
        system_region_lookup: dict[str, str] | None = None,
        effort_testing_region_lookup: dict[str, list[tuple[str, object]]] | None = None,
    ) -> list[list[str]]:
        if location_service is None:
            return []

        clean_mode = str(mode).strip().upper()
        compare_envs = self.COMPARE_ENVS_BY_MODE.get(clean_mode, set())

        if not compare_envs:
            return []

        rows: list[list[str]] = []
        seen_elements: set[tuple[str, str, str]] = set()
        region_lookup = {
            str(system).strip().upper(): str(region).strip()
            for system, region in (system_region_lookup or {}).items()
            if str(system).strip() and str(region).strip()
        }
        testing_region_lookup = self._normalize_effort_testing_region_lookup(
            effort_testing_region_lookup,
        )

        for element in sorted(
            self._moving_elements(elements),
            key=lambda item: (
                item.project.upper(),
                item.element.upper(),
                item.type.upper(),
            ),
        ):
            element_key = (
                element.project.upper(),
                element.element.upper(),
                element.type.upper(),
            )

            if element_key in seen_elements:
                continue

            seen_elements.add(element_key)
            source_regions = self._active_testing_regions(
                element=element,
                effort_dates=effort_dates,
                effort_testing_region_lookup=testing_region_lookup,
            )

            for target_record in self._get_lower_records(
                element=element,
                location_service=location_service,
                compare_envs=compare_envs,
            ):
                testing_region = self._testing_region(
                    lower_record=target_record,
                    system_region_lookup=region_lookup,
                )
                clean_testing_region = testing_region.strip().upper()
                if clean_testing_region in source_regions:
                    continue

                rows.append(
                    [
                        release,
                        element.project,
                        element.element,
                        element.type,
                        str(element.source_row.get("Application", "")),
                        self._element_owner(element),
                        self._qual_move_date(element, effort_dates),
                        target_record.env,
                        testing_region,
                        target_record.system,
                        target_record.subsystem,
                        target_record.version,
                        target_record.ccid,
                        self._remarks(
                            element=element,
                            lower_record=target_record,
                            testing_region=clean_testing_region,
                            effort_dates=effort_dates,
                            effort_testing_region_lookup=testing_region_lookup,
                        ),
                        (
                            f"Found {element.element} {element.type} in system "
                            f"region {testing_region or 'UNKNOWN'} at "
                            f"{target_record.env} / {target_record.system} / "
                            f"{target_record.subsystem} with CCID {target_record.ccid}."
                        ),
                    ]
                )

        return sorted(
            rows,
            key=lambda row: (
                row[1].upper(),
                row[2].upper(),
                row[3].upper(),
                row[4].upper(),
                row[9].upper(),
            ),
        )

    def _get_lower_records(
        self,
        element: Element,
        location_service: MainframeLocationService,
        compare_envs: set[str],
    ) -> list[MainframeLocationRecord]:
        return [
            record
            for record in location_service.find(
                element=element.element,
                type_=element.type,
            )
            if record.env.strip().upper() in compare_envs
            and record.env.strip().upper() in self.SYSTEM_COMPARE_ENVS
        ]

    def _moving_elements(
        self,
        elements: list[Element],
    ) -> list[Element]:
        return list(elements)

    def _element_owner(
        self,
        element: Element,
    ) -> str:
        for field_name in (
            "Submitter",
            "Owner",
            "DSN ID",
            "TL",
        ):
            value = str(
                element.source_row.get(
                    field_name,
                    "",
                )
            ).strip()
            if value:
                return value

        return ""

    def _qual_move_date(
        self,
        element: Element,
        effort_dates: dict[str, str] | None,
    ) -> str:
        if not effort_dates:
            return ""

        return str(
            effort_dates.get(
                element.project,
                "",
            )
        ).strip()

    def _testing_region(
        self,
        lower_record: MainframeLocationRecord,
        system_region_lookup: dict[str, str],
    ) -> str:
        return system_region_lookup.get(
            lower_record.system.strip().upper(),
            "",
        )

    def _remarks(
        self,
        element: Element,
        lower_record: MainframeLocationRecord,
        testing_region: str,
        effort_dates: dict[str, str] | None,
        effort_testing_region_lookup: dict[str, list[tuple[str, object]]],
    ) -> str:
        record_active_regions = self._active_testing_regions_for_effort_id(
            effort_id=lower_record.ccid,
            qual_date=self._qual_move_date(element, effort_dates),
            effort_testing_region_lookup=effort_testing_region_lookup,
        )

        if testing_region and testing_region in record_active_regions:
            return "plan for retrofit"

        if not self._record_ccid_matches_effort(
            lower_record=lower_record,
            effort_id=element.project,
        ):
            return "plan for retrofit"

        return "plan to delete - no authorized sandbox"

    def _active_testing_regions(
        self,
        element: Element,
        effort_dates: dict[str, str] | None,
        effort_testing_region_lookup: dict[str, list[tuple[str, object]]],
    ) -> set[str]:
        return self._active_testing_regions_for_effort_id(
            effort_id=element.project,
            qual_date=self._qual_move_date(
                element,
                effort_dates,
            ),
            effort_testing_region_lookup=effort_testing_region_lookup,
        )

    def _active_testing_regions_for_effort_id(
        self,
        effort_id: str,
        qual_date: str,
        effort_testing_region_lookup: dict[str, list[tuple[str, object]]],
    ) -> set[str]:
        move_date = coerce_date(qual_date)

        if move_date is None:
            return set()

        regions: set[str] = set()
        for region, exit_date_value in self._testing_region_assignments(
            effort_id=effort_id,
            effort_testing_region_lookup=effort_testing_region_lookup,
        ):
            exit_date = coerce_date(exit_date_value)
            if exit_date is None or exit_date < move_date:
                continue

            clean_region = str(region).strip().upper()
            if clean_region:
                regions.add(clean_region)

        return regions

    def _testing_region_assignments(
        self,
        effort_id: str,
        effort_testing_region_lookup: dict[str, list[tuple[str, object]]],
    ) -> list[tuple[str, object]]:
        clean_effort_id = str(effort_id).strip().upper()
        if not clean_effort_id:
            return []

        assignments = list(effort_testing_region_lookup.get(clean_effort_id, []))
        if len(clean_effort_id) > 6:
            assignments.extend(
                effort_testing_region_lookup.get(clean_effort_id[:6], [])
            )

        return assignments

    def _normalize_effort_testing_region_lookup(
        self,
        effort_testing_region_lookup: dict[str, list[tuple[str, object]]] | None,
    ) -> dict[str, list[tuple[str, object]]]:
        normalized: dict[str, list[tuple[str, object]]] = {}

        for effort_id, assignments in (effort_testing_region_lookup or {}).items():
            clean_effort_id = str(effort_id).strip().upper()
            if not clean_effort_id:
                continue

            normalized[clean_effort_id] = [
                (
                    str(region).strip(),
                    exit_date,
                )
                for region, exit_date in assignments
                if str(region).strip()
            ]

        return normalized

    def _record_ccid_matches_effort(
        self,
        lower_record: MainframeLocationRecord,
        effort_id: str,
    ) -> bool:
        clean_ccid = lower_record.ccid.strip().upper()
        clean_effort = effort_id.strip().upper()

        return bool(clean_ccid and clean_effort and clean_effort.startswith(clean_ccid))
