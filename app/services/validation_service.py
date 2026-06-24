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
from app.core.models import MovementStatus
from app.core.models import ReleaseEffort
from app.core.models import ScheduleStatus
from app.core.status_messages import ReasonBuilder
from app.services.mainframe_location_service import MainframeLocationService
from app.services.status_marker_service import StatusMarkerService
from app.services.validation_rules import inventory_rules as inventory_rule_module
from app.services.validation_rules import location_rules as location_rule_module
from app.services.validation_rules import movement_rules as movement_rule_module
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
        location_rule_module.apply(
            elements=elements,
            location_service=location_service,
            selection_rules_config=self.selection_rules,
            mode=mode,
            add_reason=self.add_reason,
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
        movement_rule_module.apply(
            elements=elements,
            location_service=location_service,
            status_marker_service=self.status_marker_service,
            mode=mode,
            add_reason=self.add_reason,
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
        return movement_rule_module.get_target_env(mode)

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
        return location_rule_module.get_source_env_for_move(
            mode=mode,
            element=element,
        )

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
        return location_rule_module.get_expected_system_for_move(
            mode=mode,
            element=element,
        )

    def get_expected_subsystem_for_move(
        self,
        mode: str,
        element: Element,
    ) -> str:
        return location_rule_module.get_expected_subsystem_for_move(
            mode=mode,
            element=element,
        )

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

