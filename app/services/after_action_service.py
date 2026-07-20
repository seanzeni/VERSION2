from __future__ import annotations

# Purpose:
#     Build after-action report files for bundles executed on a selected date.

from datetime import date
from pathlib import Path
from typing import Any

from app.core.models import Element
from app.core.models import MainframeLocationRecord
from app.core.models import ReleaseEffort
from app.core.package_rules import is_archive_package
from app.reports.after_action_report import AfterActionReport
from app.reports.after_action_report import build_after_action_row
from app.reports.after_action_report import parse_report_date
from app.reports.report_utils import archive_existing_reports


class AfterActionService:
    def __init__(
        self,
        context: Any,
    ) -> None:
        self.context = context

    def generate(
        self,
        selected_date: date,
        output_folder: Path,
        formats: list[str],
    ) -> list[Path]:
        output_folder.mkdir(
            parents=True,
            exist_ok=True,
        )
        archive_existing_reports(output_folder)

        rows = self._build_rows(selected_date)
        report = AfterActionReport()
        generated_files: list[Path] = []

        if "csv" in formats:
            generated_files.append(
                report.generate(
                    rows=rows,
                    output_folder=output_folder,
                )
            )

        if "xlsx" in formats:
            generated_files.append(
                report.generate_xlsx(
                    rows=rows,
                    output_folder=output_folder,
                )
            )

        if "pdf" in formats:
            generated_files.append(
                report.generate_pdf(
                    rows=rows,
                    output_folder=output_folder,
                    selected_date=selected_date,
                )
            )

        return generated_files

    def _build_rows(
        self,
        selected_date: date,
    ) -> list[list[object]]:
        rows: list[list[object]] = []

        for release in self.context.data_loader.get_releases():
            efforts = self.context.db_service.get_efforts_for_release(release)
            for mode in ("QUAL", "PROD"):
                matching_efforts = [
                    effort
                    for effort in efforts
                    if self._effort_move_date(effort, mode) == selected_date
                ]
                if not matching_efforts:
                    continue

                projects = {
                    effort.effort_id.strip()
                    for effort in matching_efforts
                    if effort.effort_id.strip()
                }
                release_df = self.context.data_loader.filter_release_projects(
                    release=release,
                    projects=projects,
                )
                elements = self.context.element_service.build_elements(release_df)

                for element in sorted(
                    elements,
                    key=lambda item: (
                        item.project.upper(),
                        item.element.upper(),
                        item.type.upper(),
                    ),
                ):
                    expected_env = self._target_env(mode)
                    expected_system = self._expected_system(mode, element)
                    expected_subsystem = self._expected_subsystem(element)
                    rows.append(
                        self._build_element_row(
                            release=release,
                            mode=mode,
                            move_date=selected_date,
                            element=element,
                            expected_env=expected_env,
                            expected_system=expected_system,
                            expected_subsystem=expected_subsystem,
                        )
                    )

        return rows

    def _build_element_row(
        self,
        release: str,
        mode: str,
        move_date: date,
        element: Element,
        expected_env: str,
        expected_system: str,
        expected_subsystem: str,
    ) -> list[object]:
        marker_service = getattr(
            self.context,
            "status_marker_service",
            None,
        )

        if marker_service is not None and marker_service.is_do_not_move(element):
            return build_after_action_row(
                release=release,
                mode=mode,
                move_date=move_date,
                element=element,
                expected_env=expected_env,
                expected_system=expected_system,
                expected_subsystem=expected_subsystem,
                record=None,
                moved_on_date="No",
                reason="Told us not to move.",
            )

        marker_record = self._find_marked_environment_record(
            element=element,
            expected_system=expected_system,
            expected_subsystem=expected_subsystem,
        )
        if marker_record is not None:
            return build_after_action_row(
                release=release,
                mode=mode,
                move_date=move_date,
                element=element,
                expected_env=marker_record.env,
                expected_system=marker_record.system,
                expected_subsystem=marker_record.subsystem,
                record=marker_record,
                moved_on_date="No",
                reason="Was moved outside of release.",
            )

        if (
            mode.upper() == "PROD"
            and is_archive_package(
                element.source_row.get(
                    "Package",
                    "",
                )
            )
            and not self._exists_in_env(
                element=element,
                env="PROD1",
            )
        ):
            return build_after_action_row(
                release=release,
                mode=mode,
                move_date=move_date,
                element=element,
                expected_env=expected_env,
                expected_system=expected_system,
                expected_subsystem=expected_subsystem,
                record=None,
                moved_on_date="No",
                reason="Archived Requested - confirmed no longer in Prod",
            )

        record = self._find_matching_record(
            element=element,
            mode=mode,
            selected_date=move_date,
            expected_env=expected_env,
            expected_system=expected_system,
            expected_subsystem=expected_subsystem,
        )
        reason = "OK"
        if record is None:
            last_move_record = self._find_last_move_record(
                element=element,
                mode=mode,
                expected_env=expected_env,
                expected_system=expected_system,
                expected_subsystem=expected_subsystem,
            )
            reason = self._missing_move_reason(
                element=element,
                last_move_record=last_move_record,
            )

        return build_after_action_row(
            release=release,
            mode=mode,
            move_date=move_date,
            element=element,
            expected_env=expected_env,
            expected_system=expected_system,
            expected_subsystem=expected_subsystem,
            record=record,
            reason=reason,
        )

    def _find_matching_record(
        self,
        element: Element,
        mode: str,
        selected_date: date,
        expected_env: str,
        expected_system: str,
        expected_subsystem: str,
    ) -> MainframeLocationRecord | None:
        location_service = self.context.location_service

        if location_service is None:
            return None

        records = [
            record
            for record in location_service.find(
                element.element,
                element.type,
            )
            if record.env.strip().upper() == expected_env
            and parse_report_date(record.date_generated) == selected_date
        ]

        if mode.upper() == "PROD":
            records = [
                record
                for record in records
                if record.system.strip().upper() == expected_system
                and record.subsystem.strip().upper() == expected_subsystem
            ]

        if not records:
            return None

        return sorted(
            records,
            key=lambda record: record.time_generated,
            reverse=True,
        )[0]

    def _find_last_move_record(
        self,
        element: Element,
        mode: str,
        expected_env: str,
        expected_system: str,
        expected_subsystem: str,
    ) -> MainframeLocationRecord | None:
        location_service = self.context.location_service

        if location_service is None:
            return None

        records = [
            record
            for record in location_service.find(
                element.element,
                element.type,
            )
            if record.env.strip().upper() == expected_env
            and parse_report_date(record.date_generated) is not None
        ]

        if mode.upper() == "PROD":
            records = [
                record
                for record in records
                if record.system.strip().upper() == expected_system
                and record.subsystem.strip().upper() == expected_subsystem
            ]

        if not records:
            return None

        return sorted(
            records,
            key=lambda record: (
                parse_report_date(record.date_generated) or date.min,
                record.time_generated,
            ),
            reverse=True,
        )[0]

    def _missing_move_reason(
        self,
        element: Element,
        last_move_record: MainframeLocationRecord | None,
    ) -> str:
        if last_move_record is None:
            return (
                "No move detected for this date. No prior NDVR move was found "
                "for this expected location."
            )

        last_move_date = parse_report_date(last_move_record.date_generated)
        last_move_text = (
            last_move_date.isoformat()
            if last_move_date is not None
            else str(last_move_record.date_generated).strip()
        )
        associated_text = (
            "Yes"
            if self._is_associated_with_inventory_project(
                element=element,
                record=last_move_record,
            )
            else "No"
        )

        return (
            "No move detected for this date. "
            f"Last move was {last_move_text} using package "
            f"{last_move_record.ndvr_package or 'Unknown'}. "
            f"Associated with inventory project {element.project}: {associated_text}."
        )

    def _is_associated_with_inventory_project(
        self,
        element: Element,
        record: MainframeLocationRecord,
    ) -> bool:
        project = str(element.project).strip().upper()
        package = str(record.ndvr_package).strip().upper()

        if not project or not package:
            return False

        return project.startswith(package) or package.startswith(project)

    def _find_marked_environment_record(
        self,
        element: Element,
        expected_system: str,
        expected_subsystem: str,
    ) -> MainframeLocationRecord | None:
        marker_service = getattr(
            self.context,
            "status_marker_service",
            None,
        )
        location_service = self.context.location_service

        if marker_service is None or location_service is None:
            return None

        records: list[MainframeLocationRecord] = []
        for env, _label in marker_service.get_marked_environments(element):
            env_records = [
                record
                for record in location_service.find(
                    element.element,
                    element.type,
                )
                if record.env.strip().upper() == env
            ]
            if env == "PROD1":
                env_records = [
                    record
                    for record in env_records
                    if record.system.strip().upper() == expected_system
                    and record.subsystem.strip().upper() == expected_subsystem
                ]
            records.extend(env_records)

        if not records:
            return None

        return sorted(
            records,
            key=lambda record: (
                parse_report_date(record.date_generated) or date.min,
                record.time_generated,
            ),
            reverse=True,
        )[0]

    def _exists_in_env(
        self,
        element: Element,
        env: str,
    ) -> bool:
        location_service = self.context.location_service

        if location_service is None:
            return False

        return location_service.exists_in_env(
            element=element.element,
            type_=element.type,
            env=env,
        )

    def _effort_move_date(
        self,
        effort: ReleaseEffort,
        mode: str,
    ) -> date | None:
        if mode.upper() == "PROD":
            return parse_report_date(effort.prod_date)

        return parse_report_date(effort.qual_date)

    def _target_env(
        self,
        mode: str,
    ) -> str:
        return "PROD1" if mode.upper() == "PROD" else "QUAL1"

    def _expected_system(
        self,
        mode: str,
        element: Element,
    ) -> str:
        system_value = str(
            element.source_row.get(
                "System",
                "",
            )
        ).strip().upper()

        if mode.upper() == "PROD" and system_value:
            return system_value[:7] + "1"

        return system_value

    def _expected_subsystem(
        self,
        element: Element,
    ) -> str:
        return str(
            element.source_row.get(
                "Subsys",
                "",
            )
        ).strip().upper()
