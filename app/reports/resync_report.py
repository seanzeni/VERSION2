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
#     - Report lower records when the selected move source has a newer version.
#     - Exclude FIXP1 from resync comparisons.

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
from app.services.validation_rules import location_rules


class ResyncReport:
    FILE_NAME = "Resync_Report.csv"
    PDF_FILE_NAME = "Resync_Report.pdf"
    TARGET_ENV_BY_MODE = {
        "QUAL": "QUAL1",
        "PROD": "PROD1",
    }
    COMPARE_ENVS_BY_MODE = {
        "QUAL": {"MAIN1", "DEVL1", "UNIT1", "UTDV1", "SYST1", "STDV1"},
        "PROD": {"MAIN1", "DEVL1", "UNIT1", "UTDV1", "SYST1", "STDV1", "QUAL1"},
    }

    def generate(
        self,
        release: str,
        mode: str,
        elements: list[Element],
        location_service: MainframeLocationService | None,
        output_folder: Path,
        effort_dates: dict[str, str] | None = None,
        tracked_elements: list[Element] | None = None,
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
                    "Lower Copy",
                    "Newer Source",
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
                        f"{row[7]} {row[10]} {row[11]}",
                        f"{row[12]} {row[15]} {row[16]}",
                        row[17],
                        row[18],
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
                    1.5 * 72,
                    1.5 * 72,
                    1.2 * 72,
                    2.2 * 72,
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
    ) -> list[list[str]]:
        if location_service is None:
            return []

        clean_mode = str(mode).strip().upper()
        target_env = self.TARGET_ENV_BY_MODE.get(clean_mode)
        compare_envs = self.COMPARE_ENVS_BY_MODE.get(clean_mode, set())

        if target_env is None:
            return []

        rows: list[list[str]] = []
        seen_elements: set[tuple[str, str, str]] = set()
        inventory_elements = tracked_elements or elements

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

            source_record = self._get_newer_source_record(
                element=element,
                location_service=location_service,
                mode=clean_mode,
                target_env=target_env,
            )

            if source_record is None:
                continue

            moving_record_keys = self._moving_record_keys(
                element=element,
                mode=clean_mode,
            )

            for target_record in self._get_lower_records(
                element=element,
                location_service=location_service,
                compare_envs=compare_envs,
                moving_record_keys=moving_record_keys,
            ):
                if source_record.version_number <= target_record.version_number:
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
                        target_record.system,
                        target_record.subsystem,
                        target_record.version,
                        target_record.ccid,
                        source_record.env,
                        source_record.system,
                        source_record.subsystem,
                        source_record.version,
                        source_record.ccid,
                        self._remarks(
                            element=element,
                            lower_record=target_record,
                            tracked_elements=inventory_elements,
                            effort_dates=effort_dates,
                        ),
                        (
                            f"{source_record.env} has newer version "
                            f"{source_record.version}; lower environment "
                            f"{target_record.env} has {target_record.version}."
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

    def _get_newer_source_record(
        self,
        element: Element,
        location_service: MainframeLocationService,
        mode: str,
        target_env: str,
    ) -> MainframeLocationRecord | None:
        if mode == "QUAL":
            return self._get_qual_move_source_record(
                element=element,
                location_service=location_service,
            )

        target_records = [
            record
            for record in location_service.find(
                element=element.element,
                type_=element.type,
            )
            if record.env.strip().upper() == target_env
        ]

        if not target_records:
            return None

        return max(
            target_records,
            key=lambda record: record.version_number,
        )

    def _get_qual_move_source_record(
        self,
        element: Element,
        location_service: MainframeLocationService,
    ) -> MainframeLocationRecord | None:
        moving_record_keys = self._moving_record_keys(
            element=element,
            mode="QUAL",
        )
        source_records = [
            record
            for record in location_service.find(
                element=element.element,
                type_=element.type,
            )
            if self._record_location_key(record) in moving_record_keys
        ]

        if not source_records:
            return None

        return max(
            source_records,
            key=lambda record: record.version_number,
        )

    def _get_lower_records(
        self,
        element: Element,
        location_service: MainframeLocationService,
        compare_envs: set[str],
        moving_record_keys: set[tuple[str, str, str]],
    ) -> list[MainframeLocationRecord]:
        return [
            record
            for record in location_service.find(
                element=element.element,
                type_=element.type,
            )
            if record.env.strip().upper() in compare_envs
            and self._record_location_key(record) not in moving_record_keys
        ]

    def _moving_record_keys(
        self,
        element: Element,
        mode: str,
    ) -> set[tuple[str, str, str]]:
        source_env = location_rules.get_source_env_for_move(
            mode=mode,
            element=element,
        )
        source_envs = location_rules.get_source_envs_for_move(
            mode=mode,
            element=element,
        )

        compare_envs = self.COMPARE_ENVS_BY_MODE.get(mode, set())
        matching_envs = {
            env.strip().upper()
            for env in source_envs
            if env.strip().upper() in compare_envs
        }
        if source_env.upper() in compare_envs:
            matching_envs.add(source_env.upper())

        return {
            (
                env,
                location_rules.get_expected_system_for_move(
                    mode=mode,
                    element=element,
                )
                .strip()
                .upper(),
                location_rules.get_expected_subsystem_for_move(
                    mode=mode,
                    element=element,
                )
                .strip()
                .upper(),
            )
            for env in matching_envs
        }

    def _record_location_key(
        self,
        record: MainframeLocationRecord,
    ) -> tuple[str, str, str]:
        return (
            record.env.strip().upper(),
            record.system.strip().upper(),
            record.subsystem.strip().upper(),
        )

    def _moving_elements(
        self,
        elements: list[Element],
    ) -> list[Element]:
        return [
            element
            for element in elements
            if element.visible and element.selected and element.selectable
        ]

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

    def _remarks(
        self,
        element: Element,
        lower_record: MainframeLocationRecord,
        tracked_elements: list[Element],
        effort_dates: dict[str, str] | None,
    ) -> str:
        if self._has_later_tracked_effort(
            element=element,
            lower_record=lower_record,
            tracked_elements=tracked_elements,
            effort_dates=effort_dates,
        ):
            return "plan for retrofit"

        return "plan to delete"

    def _has_later_tracked_effort(
        self,
        element: Element,
        lower_record: MainframeLocationRecord,
        tracked_elements: list[Element],
        effort_dates: dict[str, str] | None,
    ) -> bool:
        current_date = coerce_date(
            self._qual_move_date(
                element=element,
                effort_dates=effort_dates,
            )
        )

        for candidate in tracked_elements:
            if candidate.project.strip().upper() == element.project.strip().upper():
                continue

            if candidate.element.strip().upper() != element.element.strip().upper():
                continue

            if candidate.type.strip().upper() != element.type.strip().upper():
                continue

            candidate_date = coerce_date(
                self._qual_move_date(
                    element=candidate,
                    effort_dates=effort_dates,
                )
            )
            if current_date is not None and candidate_date is not None:
                if candidate_date <= current_date:
                    continue

            if self._record_ccid_matches_effort(
                lower_record=lower_record,
                effort_id=candidate.project,
            ):
                return True

            if not lower_record.ccid.strip():
                return True

        return False

    def _record_ccid_matches_effort(
        self,
        lower_record: MainframeLocationRecord,
        effort_id: str,
    ) -> bool:
        clean_ccid = lower_record.ccid.strip().upper()
        clean_effort = effort_id.strip().upper()

        return bool(clean_ccid and clean_effort and clean_effort.startswith(clean_ccid))
