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

from app.core.models import ArchiveStatus
from app.core.models import Element
from app.core.models import FixStatus
from app.core.models import InventoryIssue
from app.core.models import LocationStatus
from app.core.models import MovementStatus
from app.core.models import ReleaseEffort
from app.core.models import ScheduleStatus
from app.core.status_messages import ReasonBuilder
from app.services.mainframe_location_service import MainframeLocationService
from app.services.status_marker_service import StatusMarkerService
from app.services.validation_rules import inventory_rules as inventory_rule_module
from app.services.validation_rules import schedule_rules as schedule_rule_module
from app.services.validation_rules import selection_rules as selection_rule_module


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
        inventory_rule_module.apply(
            elements=elements,
            add_reason=self.add_reason,
        )

    def apply_schedule_status(
        self,
        elements: list[Element],
        release_efforts: list[ReleaseEffort],
        effort_release_lookup: dict[str, str],
        release: str,
    ) -> None:
        schedule_rule_module.apply(
            elements=elements,
            release_efforts=release_efforts,
            effort_release_lookup=effort_release_lookup,
            release=release,
            add_reason=self.add_reason,
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
        return schedule_rule_module.build_inventory_issues(
            release=release,
            all_release_elements=all_release_elements,
            release_efforts=release_efforts,
        )

    def apply_selection_rules(
        self,
        elements: list[Element],
        mode: str = "",
    ) -> None:
        selection_rule_module.apply(
            elements=elements,
            selection_rules=self.selection_rules,
            mode=mode,
        )

    def is_confirmed_already_in_target(
        self,
        element: Element,
    ) -> bool:
        return bool(
            selection_rule_module.is_confirmed_already_in_target(element)
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
            selection_rule_module.is_archive_type_for_qual_move(
                mode=mode,
                element=element,
                selection_rules=self.selection_rules,
            )
        )

    def is_archive_move(
        self,
        element: Element,
    ) -> bool:
        return selection_rule_module.is_archive_move(element)

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

