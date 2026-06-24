from __future__ import annotations

"""
Purpose:
    Apply validation statuses and selection rules to inventory elements.

Used By:
    MainWindow
    Reports

Responsibilities:
    - Detect overlaps and duplicates.
    - Compare inventory efforts to SQL release schedule.
    - Validate expected NDVR/mainframe location.
    - Apply archive/program-move warnings.
    - Apply movement marker rules.
    - Apply FIXP1 warning.
    - Apply selected/selectable rules.

Notes:
    This is the main business validation service.
    It should not query SQL directly.
    It should not read Excel directly.
    It should not build reports.
"""

from collections import defaultdict

from app.core.models import ArchiveStatus
from app.core.models import Element
from app.core.models import FixStatus
from app.core.models import InventoryIssue
from app.core.models import InventoryStatus
from app.core.models import LocationStatus
from app.core.models import MovementStatus
from app.core.models import ReleaseEffort
from app.core.models import ScheduleStatus
from app.core.package_rules import is_archive_package
from app.core.status_messages import ReasonBuilder
from app.services.mainframe_location_service import MainframeLocationService
from app.services.status_marker_service import StatusMarkerService


class ValidationService:
    def __init__(
        self,
        selection_rules: dict,
        archive_pairs: list[list[str]],
        status_marker_service: StatusMarkerService,
    ) -> None:
        self.selection_rules = selection_rules
        self.archive_pairs = archive_pairs
        self.status_marker_service = status_marker_service

    def validate_elements(
        self,
        elements: list[Element],
        all_release_elements: list[Element],
        release_efforts: list[ReleaseEffort],
        effort_release_lookup: dict[str, str],
        location_service: MainframeLocationService | None,
        mode: str,
        release: str,
        skip_location_validation: bool = False,
    ) -> tuple[list[Element], list[InventoryIssue]]:

        self.apply_movement_status(
            elements=elements,
            location_service=location_service,
            mode=mode,
        )

        self.apply_overlap_duplicate_status(
            elements=elements,
        )

        self.apply_schedule_status(
            elements=elements,
            release_efforts=release_efforts,
            effort_release_lookup=effort_release_lookup,
            release=release,
        )

        if not skip_location_validation:
            self.apply_location_status(
                elements=elements,
                location_service=location_service,
                mode=mode,
            )

        self.apply_archive_status(
            elements=elements,
            location_service=location_service,
            mode=mode,
        )

        self.apply_fixp1_status(
            elements=elements,
            location_service=location_service,
            mode=mode,
        )

        self.apply_selection_rules(
            elements=elements,
            mode=mode,
        )

        inventory_issues = self.build_inventory_issues(
            release=release,
            all_release_elements=all_release_elements,
            release_efforts=release_efforts,
        )

        return elements, inventory_issues

    def add_reason(
        self,
        element: Element,
        reason: str,
    ) -> None:
        if reason and reason not in element.reasons:
            element.reasons.append(reason)

    def apply_overlap_duplicate_status(
        self,
        elements: list[Element],
    ) -> None:
        grouped: dict[tuple[str, str], list[Element]] = defaultdict(list)

        for element in elements:
            if element.movement_status != MovementStatus.DO_NOT_MOVE:
                # Skip those elements that are marked do not move
                grouped[element.key].append(element)

        for group in grouped.values():
            projects = {element.project for element in group}
            project_counts: dict[str, int] = defaultdict(int)

            for element in group:
                project_counts[element.project] += 1

            if len(projects) > 1:
                for element in group:
                    element.inventory_status = InventoryStatus.OVERLAP

                    self.add_reason(
                        element=element,
                        reason=ReasonBuilder.overlap(
                            element=element.element,
                            type_=element.type,
                            project=element.project,
                            other_projects=sorted(
                                project
                                for project in projects
                                if project != element.project
                            ),
                        ),
                    )

                    if project_counts[element.project] > 1:
                        self.add_reason(
                            element=element,
                            reason=ReasonBuilder.duplicate(
                                element=element.element,
                                type_=element.type,
                                project=element.project,
                            ),
                        )

            elif len(group) > 1:
                for element in group:
                    element.inventory_status = InventoryStatus.DUPLICATE

                    self.add_reason(
                        element=element,
                        reason=ReasonBuilder.duplicate(
                            element=element.element,
                            type_=element.type,
                            project=element.project,
                        ),
                    )

    def apply_schedule_status(
        self,
        elements: list[Element],
        release_efforts: list[ReleaseEffort],
        effort_release_lookup: dict[str, str],
        release: str,
    ) -> None:
        release_effort_ids = {
            effort.effort_id.strip()
            for effort in release_efforts
            if effort.effort_id.strip()
        }

        no_inventory_effort_ids = {
            effort.effort_id.strip()
            for effort in release_efforts
            if effort.no_inventory and effort.effort_id.strip()
        }

        for element in elements:
            effort_id = element.project.strip()
            sql_release = effort_release_lookup.get(
                effort_id,
            )

            if sql_release and sql_release.upper() != element.release.upper():
                element.schedule_status = ScheduleStatus.EFFORT_RELEASE_MISMATCH

                self.add_reason(
                    element=element,
                    reason=ReasonBuilder.effort_release_mismatch(
                        project=element.project,
                        inventory_release=element.release,
                        sql_release=sql_release,
                    ),
                )

                continue

            if effort_id in no_inventory_effort_ids:
                element.schedule_status = ScheduleStatus.INVENTORY_WHEN_SQL_NO_INVENTORY

                self.add_reason(
                    element=element,
                    reason=ReasonBuilder.inventory_when_sql_no_inventory(
                        project=element.project,
                        release=release,
                    ),
                )

                continue

            if effort_id not in release_effort_ids:
                element.schedule_status = ScheduleStatus.INVENTORY_NOT_IN_RELEASE

                self.add_reason(
                    element=element,
                    reason=ReasonBuilder.inventory_not_in_release(
                        project=element.project,
                        release=release,
                    ),
                )

    def apply_location_status(
        self,
        elements: list[Element],
        location_service: MainframeLocationService | None,
        mode: str,
    ) -> None:
        if location_service is None:
            return

        for element in elements:
            if element.movement_status == MovementStatus.DO_NOT_MOVE:
                continue

            if self.is_archive_type_for_qual_move(
                mode=mode,
                element=element,
            ) and element.schedule_status == ScheduleStatus.OK:
                continue

            expected_env = self.get_source_env_for_move(
                mode=mode,
                element=element,
            )
            expected_system = self.get_expected_system_for_move(
                mode=mode,
                element=element,
            )
            expected_subsystem = self.get_expected_subsystem_for_move(
                mode=mode,
                element=element,
            )

            if location_service.exists_in_location(
                element=element.element,
                type_=element.type,
                env=expected_env,
                system=expected_system,
                subsystem=expected_subsystem,
            ):
                element.location_status = LocationStatus.FOUND
                continue

            expected_level = self.get_env_level(
                env=expected_env,
            )

            found_records = [
                record
                for record in location_service.find(
                    element=element.element,
                    type_=element.type,
                )
                if self.get_env_level(record.env) < expected_level
            ]
            found_locations = [
                f"{record.env} / {record.system} / {record.subsystem}"
                for record in found_records
            ]

            element.location_status = LocationStatus.NOT_FOUND

            self.add_reason(
                element=element,
                reason=ReasonBuilder.missing_ndvr(
                    element=element.element,
                    type_=element.type,
                    expected_env=expected_env,
                    expected_system=expected_system,
                    expected_subsystem=expected_subsystem,
                    found_locations=found_locations,
                ),
            )

    def apply_archive_status(
        self,
        elements: list[Element],
        location_service: MainframeLocationService | None,
        mode: str,
    ) -> None:
        if mode.upper() != "PROD":
            return

        if location_service is None:
            return

        inventory_lookup = {element.key for element in elements}

        for element in elements:
            if element.movement_status == MovementStatus.DO_NOT_MOVE:
                continue

            element_name = element.element.strip().upper()
            element_type = element.type.strip().upper()

            opposite_type = self.get_opposite_type(
                type_name=element_type,
            )

            # Rule 1:
            # Moving to PROD.
            # Opposite type exists in PROD1.
            # Opposite type is not present in selected inventory.
            # Example:
            #   Moving OCOB
            #   PROD1 has OAPS
            #   Inventory missing OAPS
            if opposite_type is None:
                continue

            if location_service.exists_in_env(
                element=element_name,
                type_=opposite_type,
                env="PROD1",
            ):
                if (
                    element_name,
                    opposite_type,
                ) not in inventory_lookup:
                    element.archive_status = ArchiveStatus.POTENTIAL_MISSING_ARCHIVE

                    self.add_reason(
                        element=element,
                        reason=ReasonBuilder.potential_missing_archive(
                            element=element.element,
                            moving_type=element.type,
                            opposite_type=opposite_type,
                            env="PROD1",
                        ),
                    )

            # Rule 2:
            # Moving to PROD.
            # Current inventory row is the archive side.
            # Opposite program type is not present in selected inventory.
            # Example:
            #   Moving OAPS archive
            #   Inventory missing OCOB
            program_type = self.get_program_type_for_archive(
                archive_type=element_type,
            )

            if program_type is None or not self.is_archive_move(element):
                continue

            if (
                element_name,
                program_type,
            ) in inventory_lookup:
                continue

            found_env = (
                "QUAL1"
                if location_service.exists_in_env(
                    element=element_name,
                    type_=program_type,
                    env="QUAL1",
                )
                else ""
            )

            element.archive_status = ArchiveStatus.POTENTIAL_MISSING_PROGRAM_MOVE

            self.add_reason(
                element=element,
                reason=ReasonBuilder.potential_missing_program_move(
                    element=element.element,
                    archive_type=element.type,
                    program_type=program_type,
                    env=found_env,
                ),
            )

    def apply_fixp1_status(
        self,
        elements: list[Element],
        location_service: MainframeLocationService | None,
        mode: str,
    ) -> None:
        if mode.upper() != "PROD":
            return

        if location_service is None:
            return

        for element in elements:
            if location_service.exists_in_fixp1(
                element=element.element,
                type_=element.type,
            ):
                element.fix_status = FixStatus.EXISTS_IN_FIXP1

                self.add_reason(
                    element=element,
                    reason=ReasonBuilder.exists_in_fixp1(
                        element=element.element,
                        type_=element.type,
                    ),
                )

    def apply_movement_status(
        self,
        elements: list[Element],
        location_service: MainframeLocationService | None,
        mode: str,
    ) -> None:
        target_env = self.get_target_env(
            mode=mode,
        )

        for element in elements:
            if self.status_marker_service.is_do_not_move(
                element=element,
            ):
                element.movement_status = MovementStatus.DO_NOT_MOVE

                self.add_reason(
                    element=element,
                    reason=ReasonBuilder.do_not_move(
                        element=element.element,
                        type_=element.type,
                        marker_text="DO NOT MOVE",
                    ),
                )

                continue

            if not self.status_marker_service.is_marked_for_target(
                element=element,
                mode=mode,
            ):
                continue

            if location_service is not None and location_service.exists_in_env(
                element=element.element,
                type_=element.type,
                env=target_env,
            ):
                element.source_row["_confirmed_already_in_target"] = True
                # Marker says already there and NDVR confirms it.
                # This should not show as an issue.
                # Selection rules will hide/unselect it by marker check.
                continue

            marker_text = self.status_marker_service.get_target_marker_text(
                element=element,
                mode=mode,
            )

            element.movement_status = MovementStatus.MARKED_ALREADY_THERE_BUT_MISSING

            self.add_reason(
                element=element,
                reason=ReasonBuilder.marked_already_there_but_missing(
                    element=element.element,
                    type_=element.type,
                    target_env=target_env,
                    marker_text=marker_text,
                ),
            )

    def build_inventory_issues(
        self,
        release: str,
        all_release_elements: list[Element],
        release_efforts: list[ReleaseEffort],
    ) -> list[InventoryIssue]:
        inventory_effort_ids = {
            element.project.strip()
            for element in all_release_elements
            if element.project.strip()
        }

        issues: list[InventoryIssue] = []

        for effort in release_efforts:
            effort_id = effort.effort_id.strip()

            if not effort_id:
                continue

            if effort.no_inventory:
                continue

            if effort_id not in inventory_effort_ids:
                issues.append(
                    InventoryIssue(
                        release=release,
                        effort_id=effort_id,
                        issue_type=ScheduleStatus.SQL_EXPECTED_INVENTORY_MISSING,
                        reason=ReasonBuilder.sql_expected_inventory_missing(
                            project=effort_id,
                            release=release,
                        ),
                        expected_release=release,
                        inventory_release="",
                    )
                )

        return issues

    def apply_selection_rules(
        self,
        elements: list[Element],
        mode: str = "",
    ) -> None:
        for element in elements:
            element.selected = True
            element.selectable = True

            if self.is_archive_type_for_qual_move(
                mode=mode,
                element=element,
            ) and element.schedule_status == ScheduleStatus.OK:
                element.selected = False
                element.selectable = False
                element.visible = False
                continue

            if element.inventory_status == InventoryStatus.OVERLAP:
                element.selected = False
                element.selectable = bool(
                    self.selection_rules.get(
                        "overlap_selectable",
                        False,
                    )
                )

            if element.inventory_status == InventoryStatus.DUPLICATE:
                element.selected = False
                element.selectable = bool(
                    self.selection_rules.get(
                        "duplicate_selectable",
                        False,
                    )
                )

            if element.schedule_status == ScheduleStatus.INVENTORY_NOT_IN_RELEASE:
                element.selected = False
                element.selectable = bool(
                    self.selection_rules.get(
                        "inventory_not_in_release_selectable",
                        True,
                    )
                )

            if (
                element.schedule_status
                == ScheduleStatus.INVENTORY_WHEN_SQL_NO_INVENTORY
            ):
                element.selected = False
                element.selectable = bool(
                    self.selection_rules.get(
                        "inventory_when_sql_no_inventory_selectable",
                        True,
                    )
                )

            if element.schedule_status == ScheduleStatus.EFFORT_RELEASE_MISMATCH:
                element.selected = False
                element.selectable = bool(
                    self.selection_rules.get(
                        "effort_release_mismatch_selectable",
                        True,
                    )
                )

            if element.archive_status == ArchiveStatus.POTENTIAL_MISSING_ARCHIVE:
                element.selected = False
                element.selectable = bool(
                    self.selection_rules.get(
                        "potential_missing_archive_selectable",
                        False,
                    )
                )

            if element.archive_status == ArchiveStatus.POTENTIAL_MISSING_PROGRAM_MOVE:
                element.selected = False
                element.selectable = bool(
                    self.selection_rules.get(
                        "potential_missing_program_move_selectable",
                        True,
                    )
                )

            if element.movement_status == MovementStatus.DO_NOT_MOVE:
                element.selected = False
                element.selectable = bool(
                    self.selection_rules.get(
                        "do_not_move_selectable",
                        False,
                    )
                )

            if (
                element.movement_status
                == MovementStatus.MARKED_ALREADY_THERE_BUT_MISSING
            ):
                element.selected = False
                element.selectable = bool(
                    self.selection_rules.get(
                        "marked_already_there_missing_selectable",
                        True,
                    )
                )

            if self.is_confirmed_already_in_target(
                element=element,
            ) and element.schedule_status == ScheduleStatus.OK:
                element.selected = False
                element.selectable = False
                element.visible = False

            if element.location_status == LocationStatus.NOT_FOUND:
                element.selected = False
                element.selectable = bool(
                    self.selection_rules.get(
                        "missing_ndvr_selectable",
                        False,
                    )
                )

    def is_confirmed_already_in_target(
        self,
        element: Element,
    ) -> bool:
        return bool(
            element.source_row.get(
                "_confirmed_already_in_target",
                False,
            )
        )

    def get_target_env(
        self,
        mode: str,
    ) -> str:
        if mode.upper() == "PROD":
            return "PROD1"

        return "QUAL1"

    def get_env_level(
        self,
        env: str,
    ) -> int:
        return MainframeLocationService.ENV_LEVELS.get(
            str(env).strip().upper(),
            0,
        )

    def get_source_env_for_move(
        self,
        mode: str,
        element: Element,
    ) -> str:
        if mode.upper() == "PROD":
            if self.is_archive_move(element):
                return "PROD1"

            return "QUAL1"

        act_region = str(
            element.source_row.get(
                "Act Rgn",
                "",
            )
        ).strip().upper()

        if act_region.startswith("DV"):
            return "DEVL1"

        if act_region.startswith("LO"):
            return "MAIN1"

        return "QUAL1"

    def is_archive_type_for_qual_move(
        self,
        mode: str,
        element: Element,
    ) -> bool:
        return (
            mode.upper() == "QUAL"
            and bool(
                self.selection_rules.get(
                    "hide_archive_rows_in_qual",
                    True,
                )
            )
            and self.is_archive_move(element)
        )

    def is_archive_move(
        self,
        element: Element,
    ) -> bool:
        package_value = element.source_row.get(
            "Package",
            "",
        )

        return is_archive_package(package_value)

    def get_expected_system_for_move(
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

    def get_expected_subsystem_for_move(
        self,
        mode: str,
        element: Element,
    ) -> str:
        return str(
            element.source_row.get(
                "Subsys",
                "",
            )
        ).strip().upper()

    def get_opposite_type(
        self,
        type_name: str,
    ) -> str | None:
        clean_type = str(type_name).strip().upper()

        for pair in self.archive_pairs:
            if len(pair) != 2:
                continue

            archive_type = str(pair[0]).strip().upper()

            program_type = str(pair[1]).strip().upper()

            if clean_type == archive_type:
                return program_type

            if clean_type == program_type:
                return archive_type

        return None

    def get_program_type_for_archive(
        self,
        archive_type: str,
    ) -> str | None:
        clean_type = str(archive_type).strip().upper()

        for pair in self.archive_pairs:
            if len(pair) != 2:
                continue

            archive_side = str(pair[0]).strip().upper()

            program_side = str(pair[1]).strip().upper()

            if clean_type == archive_side:
                return program_side

        return None

