from __future__ import annotations

# Purpose:
#     Build after-action report files for bundles executed on a selected date.

import tempfile
import re
from datetime import date
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.models import Element
from app.core.models import MainframeLocationRecord
from app.core.models import ReleaseEffort
from app.core.package_rules import is_archive_package
from app.reports.after_action_report import AfterActionReport
from app.reports.after_action_report import build_after_action_row
from app.reports.after_action_report import parse_report_date
from app.reports.report_utils import publish_staged_outputs
from app.reports.report_utils import report_date_stamp
from app.services.mainframe_location_service import MainframeLocationService


class AfterActionService:
    EARLY_MOVE_WINDOW_DAYS = 30
    NDVR_FILE_PATTERNS = ("*.txt", "*.dat", "*.csv")
    NDVR_FILE_DATE_PATTERN = re.compile(
        r"(?P<date>\d{8}|\d{4}[-_/]\d{2}[-_/]\d{2})"
    )

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
        effort_ids: set[str] | None = None,
    ) -> list[Path]:
        output_folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        rows = self._build_rows(
            selected_date=selected_date,
            effort_ids=effort_ids,
        )
        report = AfterActionReport()
        file_stem = f"Effort_Move_Status_{report_date_stamp(selected_date)}"

        with tempfile.TemporaryDirectory(
            prefix="after-action-",
            dir=output_folder.parent,
        ) as temp_dir:
            staged_files = self._generate_report_files(
                report=report,
                rows=rows,
                output_folder=Path(temp_dir),
                formats=formats,
                selected_date=selected_date,
                file_stem=file_stem,
            )
            return publish_staged_outputs(
                staged_files=staged_files,
                output_folder=output_folder,
                file_stems=[file_stem],
            )

    def _generate_report_files(
        self,
        report: AfterActionReport,
        rows: list[list[object]],
        output_folder: Path,
        formats: list[str],
        selected_date: date,
        file_stem: str,
    ) -> list[Path]:
        generated_files: list[Path] = []

        if "csv" in formats:
            generated_files.append(
                report.generate(
                    rows=rows,
                    output_folder=output_folder,
                    file_stem=file_stem,
                )
            )

        if "xlsx" in formats:
            generated_files.append(
                report.generate_xlsx(
                    rows=rows,
                    output_folder=output_folder,
                    file_stem=file_stem,
                )
            )

        if "pdf" in formats:
            generated_files.append(
                report.generate_pdf(
                    rows=rows,
                    output_folder=output_folder,
                    selected_date=selected_date,
                    file_stem=file_stem,
                )
            )

        return generated_files

    def _build_rows(
        self,
        selected_date: date,
        effort_ids: set[str] | None = None,
    ) -> list[list[object]]:
        rows: list[list[object]] = []
        clean_effort_ids = self._clean_effort_ids(effort_ids)
        original_location_service = self.context.location_service
        as_of_location_service = self._build_report_date_location_service(
            selected_date
        )

        if as_of_location_service is not None:
            self.context.location_service = as_of_location_service

        try:
            for release in self.context.data_loader.get_releases():
                efforts = self.context.db_service.get_efforts_for_release(release)
                for mode in ("QUAL", "PROD"):
                    matching_efforts = [
                        effort
                        for effort in efforts
                        if self._effort_move_date(effort, mode) == selected_date
                        and self._effort_is_requested(effort, clean_effort_ids)
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
                        )
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
        finally:
            self.context.location_service = original_location_service

        return rows

    def _clean_effort_ids(
        self,
        effort_ids: set[str] | None,
    ) -> set[str]:
        return {
            str(effort_id).strip().upper()
            for effort_id in (effort_ids or set())
            if str(effort_id).strip()
        }

    def _effort_is_requested(
        self,
        effort: ReleaseEffort,
        effort_ids: set[str],
    ) -> bool:
        if not effort_ids:
            return True

        return effort.effort_id.strip().upper() in effort_ids

    def _build_report_date_location_service(
        self,
        selected_date: date,
    ) -> MainframeLocationService | None:
        files = self._report_date_ndvr_files(selected_date)
        if not files:
            return None

        return MainframeLocationService().load_files(files)

    def _report_date_ndvr_files(
        self,
        selected_date: date,
    ) -> list[Path]:
        source = self._ndvr_source()
        if source is None:
            return []

        if source.is_file():
            return [source]

        if not source.is_dir():
            return []

        files_by_date: dict[date, list[Path]] = {}
        for candidate in {
            candidate
            for pattern in self.NDVR_FILE_PATTERNS
            for candidate in source.glob(pattern)
            if candidate.is_file()
        }:
            file_date = self._file_date(candidate)
            if file_date is None or file_date < selected_date:
                continue

            files_by_date.setdefault(file_date, []).append(candidate)

        if not files_by_date:
            return []

        chosen_date = (
            selected_date
            if selected_date in files_by_date
            else min(files_by_date)
        )

        return sorted(
            files_by_date[chosen_date],
            key=lambda candidate: (
                candidate.stat().st_mtime,
                candidate.name,
            ),
        )

    def _ndvr_source(
        self,
    ) -> Path | None:
        source = getattr(
            self.context,
            "ndvr_source",
            None,
        )
        if source is None:
            settings = getattr(
                self.context,
                "settings",
                {},
            )
            source = settings.get(
                "files",
                {},
            ).get(
                "default_ndvr_file",
                "",
            )

        if not str(source).strip():
            return None

        path = Path(source)
        if path.is_absolute():
            return path

        base_dir = Path(
            getattr(
                self.context,
                "base_dir",
                Path.cwd(),
            )
        )
        return base_dir / path

    def _file_date(
        self,
        file_path: Path,
    ) -> date | None:
        match = self.NDVR_FILE_DATE_PATTERN.search(file_path.name)
        if match is None:
            return None

        value = match.group("date").replace("-", "").replace("_", "").replace("/", "")
        try:
            return datetime.strptime(value, "%Y%m%d").date()
        except ValueError:
            return None

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
            as_of_date=move_date,
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
                as_of_date=move_date,
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
        evidence_record = record
        moved_on_date = None
        if record is None:
            last_move_record = self._find_last_move_record(
                element=element,
                mode=mode,
                as_of_date=move_date,
                expected_env=expected_env,
                expected_system=expected_system,
                expected_subsystem=expected_subsystem,
            )
            if last_move_record is not None:
                evidence_record = last_move_record
                moved_on_date = "No"
                reason = self._missing_move_reason(
                    element=element,
                    move_date=move_date,
                    last_move_record=last_move_record,
                )
            else:
                equal_or_higher_records = self._find_equal_or_higher_records(
                    element=element,
                    as_of_date=move_date,
                    expected_env=expected_env,
                    expected_system=expected_system,
                    expected_subsystem=expected_subsystem,
                )
                if equal_or_higher_records:
                    evidence_record = equal_or_higher_records[0]
                    moved_on_date = "No"
                    reason = self._equal_or_higher_location_reason(
                        records=equal_or_higher_records,
                    )
                else:
                    reason = self._missing_move_reason(
                        element=element,
                        move_date=move_date,
                        last_move_record=None,
                    )

        return build_after_action_row(
            release=release,
            mode=mode,
            move_date=move_date,
            element=element,
            expected_env=expected_env,
            expected_system=expected_system,
            expected_subsystem=expected_subsystem,
            record=evidence_record,
            moved_on_date=moved_on_date,
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
        as_of_date: date,
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
            and self._record_date_on_or_before(record, as_of_date)
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

    def _find_equal_or_higher_records(
        self,
        element: Element,
        as_of_date: date,
        expected_env: str,
        expected_system: str,
        expected_subsystem: str,
    ) -> list[MainframeLocationRecord]:
        location_service = self.context.location_service

        if location_service is None:
            return []

        expected_level = self._env_level(expected_env)
        records = [
            record
            for record in location_service.find(
                element.element,
                element.type,
            )
            if self._env_level(record.env) > expected_level
            and self._record_date_on_or_before(record, as_of_date)
        ]

        if expected_env.strip().upper() == "PROD1":
            records = [
                record
                for record in records
                if record.env.strip().upper() != "PROD1"
                or (
                    record.system.strip().upper() == expected_system
                    and record.subsystem.strip().upper() == expected_subsystem
                )
            ]

        return sorted(
            records,
            key=lambda record: (
                self._env_level(record.env),
                parse_report_date(record.date_generated) or date.min,
                record.time_generated,
            ),
            reverse=True,
        )

    def _equal_or_higher_location_reason(
        self,
        records: list[MainframeLocationRecord],
    ) -> str:
        locations = [self._format_found_location(record) for record in records]

        return (
            "No move detected for this date. "
            f"Found equal or higher NDVR location(s): {', '.join(locations)}."
        )

    def _format_found_location(
        self,
        record: MainframeLocationRecord,
    ) -> str:
        found_date = parse_report_date(record.date_generated)
        found_date_text = (
            found_date.isoformat()
            if found_date is not None
            else str(record.date_generated).strip()
        )
        package = str(record.ndvr_package or "").strip() or "Unknown"

        return (
            f"{record.env} / {record.system} / {record.subsystem} "
            f"on {found_date_text} using package {package}"
        )

    def _missing_move_reason(
        self,
        element: Element,
        move_date: date,
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

        if (
            last_move_date is not None
            and 0 < (move_date - last_move_date).days <= self.EARLY_MOVE_WINDOW_DAYS
        ):
            return (
                "Moved early. "
                f"Expected move date was {move_date.isoformat()}, but the "
                f"expected location was found on {last_move_text} using package "
                f"{last_move_record.ndvr_package or 'Unknown'}."
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
            f"Last package associated with Project {element.project}: "
            f"{associated_text}; currently associated with {element.project}."
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

    def _env_level(
        self,
        env: str,
    ) -> int:
        return MainframeLocationService.ENV_LEVELS.get(
            str(env).strip().upper(),
            0,
        )

    def _find_marked_environment_record(
        self,
        element: Element,
        as_of_date: date,
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
                and self._record_date_on_or_before(record, as_of_date)
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
        as_of_date: date,
    ) -> bool:
        location_service = self.context.location_service

        if location_service is None:
            return False

        return any(
            record.env.strip().upper() == env.strip().upper()
            and self._record_date_on_or_before(record, as_of_date)
            for record in location_service.find(
                element.element,
                element.type,
            )
        )

    def _record_date_on_or_before(
        self,
        record: MainframeLocationRecord,
        as_of_date: date,
    ) -> bool:
        record_date = parse_report_date(record.date_generated)
        return record_date is not None and record_date <= as_of_date

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
        system_value = (
            str(
                element.source_row.get(
                    "System",
                    "",
                )
            )
            .strip()
            .upper()
        )

        if mode.upper() == "PROD" and system_value:
            return system_value[:7] + "1"

        return system_value

    def _expected_subsystem(
        self,
        element: Element,
    ) -> str:
        return (
            str(
                element.source_row.get(
                    "Subsys",
                    "",
                )
            )
            .strip()
            .upper()
        )
