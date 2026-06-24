from __future__ import annotations

"""
Purpose:
    Apply validation statuses and selection rules to inventory elements.

Annotations:
    Uses postponed annotations for modern type hints and validation context
    construction.

Used By:
    MainWindow
    Reports

Responsibilities:
    - Orchestrate validation rules in dependency order.
    - Build ValidatorContext objects for rule execution.
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

from app.core.models import Element
from app.core.models import InventoryIssue
from app.core.models import ReleaseEffort
from app.core.models import ScheduleStatus
from app.services.mainframe_location_service import MainframeLocationService
from app.services.status_marker_service import StatusMarkerService
from app.services.validation_rules import archive_rules as archive_rule_module
from app.services.validation_rules.base import require_rule_module
from app.services.validation_rules.base import ValidatorContext
from app.services.validation_rules import fix_rules as fix_rule_module
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
        self._validate_rule_contracts()

    def _validate_rule_contracts(
        self,
    ) -> None:
        for rule_name, rule_module in {
            "archive_rules": archive_rule_module,
            "fix_rules": fix_rule_module,
            "inventory_rules": inventory_rule_module,
            "location_rules": location_rule_module,
            "movement_rules": movement_rule_module,
            "schedule_rules": schedule_rule_module,
            "selection_rules": selection_rule_module,
        }.items():
            require_rule_module(
                rule_module=rule_module,
                rule_name=rule_name,
            )

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

    def _build_context(
        self,
        elements: list[Element] | None = None,
        all_release_elements: list[Element] | None = None,
        release_efforts: list[ReleaseEffort] | None = None,
        effort_release_lookup: dict[str, str] | None = None,
        release: str = "",
        mode: str = "",
        location_service: MainframeLocationService | None = None,
    ) -> ValidatorContext:
        return ValidatorContext(
            elements=elements or [],
            all_release_elements=all_release_elements or [],
            release_efforts=release_efforts or [],
            effort_release_lookup=effort_release_lookup or {},
            release=release,
            mode=mode,
            selection_rules=self.selection_rules,
            archive_pairs=self.archive_pairs,
            location_service=location_service,
            status_marker_service=self.status_marker_service,
            add_reason=self.add_reason,
        )

    def apply_overlap_duplicate_status(
        self,
        elements: list[Element],
    ) -> None:
        inventory_rule_module.apply(
            self._build_context(
                elements=elements,
            ),
        )

    def apply_schedule_status(
        self,
        elements: list[Element],
        release_efforts: list[ReleaseEffort],
        effort_release_lookup: dict[str, str],
        release: str,
    ) -> None:
        schedule_rule_module.apply(
            self._build_context(
                elements=elements,
                release_efforts=release_efforts,
                effort_release_lookup=effort_release_lookup,
                release=release,
            ),
        )

    def apply_location_status(
        self,
        elements: list[Element],
        location_service: MainframeLocationService | None,
        mode: str,
    ) -> None:
        location_rule_module.apply(
            self._build_context(
                elements=elements,
                location_service=location_service,
                mode=mode,
            ),
        )

    def apply_archive_status(
        self,
        elements: list[Element],
        location_service: MainframeLocationService | None,
        mode: str,
    ) -> None:
        archive_rule_module.apply(
            self._build_context(
                elements=elements,
                location_service=location_service,
                mode=mode,
            ),
        )

    def apply_fixp1_status(
        self,
        elements: list[Element],
        location_service: MainframeLocationService | None,
        mode: str,
    ) -> None:
        fix_rule_module.apply(
            self._build_context(
                elements=elements,
                location_service=location_service,
                mode=mode,
            ),
        )

    def apply_movement_status(
        self,
        elements: list[Element],
        location_service: MainframeLocationService | None,
        mode: str,
    ) -> None:
        movement_rule_module.apply(
            self._build_context(
                elements=elements,
                location_service=location_service,
                mode=mode,
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
            self._build_context(
                elements=elements,
                mode=mode,
            ),
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
        return archive_rule_module.get_opposite_type(
            type_name=type_name,
            archive_pairs=self.archive_pairs,
        )

    def get_program_type_for_archive(
        self,
        archive_type: str,
    ) -> str | None:
        return archive_rule_module.get_program_type_for_archive(
            archive_type=archive_type,
            archive_pairs=self.archive_pairs,
        )

