from __future__ import annotations

# Purpose:
#     Apply validation statuses and selection rules to inventory elements.
#
# Annotations:
#     Uses postponed annotations for modern type hints and validation context
#     construction.
#
# Used By:
#     MainWindow
#     Reports
#
# Responsibilities:
#     - Orchestrate validation rules in dependency order.
#     - Build ValidatorContext objects for rule execution.
#     - Detect overlaps and duplicates.
#     - Compare inventory efforts to SQL release schedule.
#     - Validate expected NDVR/mainframe location.
#     - Apply archive/program-move warnings.
#     - Apply movement marker rules.
#     - Apply FIXP1 warning.
#     - Apply selected/selectable rules.
#
# Notes:
#     This is the main business validation service.
#     It should not query SQL directly.
#     It should not read Excel directly.
#     It should not build reports.

from app.core.models import Element
from app.core.models import InventoryIssue
from app.core.models import ReleaseEffort
from app.services.mainframe_location_service import MainframeLocationService
from app.services.reference_element_service import ReferenceElementService
from app.services.status_marker_service import StatusMarkerService
from app.services.validation_rules import awareness_rules as awareness_rule_module
from app.services.validation_rules import archive_rules as archive_rule_module
from app.services.validation_rules.base import build_rule_registry_rows
from app.services.validation_rules.base import resolve_rule_modules
from app.services.validation_rules.base import RuleModule
from app.services.validation_rules.base import ValidatorContext
from app.services.validation_rules import fix_rules as fix_rule_module
from app.services.validation_rules import inventory_rules as inventory_rule_module
from app.services.validation_rules import location_rules as location_rule_module
from app.services.validation_rules import movement_rules as movement_rule_module
from app.services.validation_rules import packaging_rules as packaging_rule_module
from app.services.validation_rules import schedule_rules as schedule_rule_module
from app.services.validation_rules import selection_rules as selection_rule_module


VALIDATION_RULE_MODULES = [
    movement_rule_module,
    inventory_rule_module,
    schedule_rule_module,
    location_rule_module,
    archive_rule_module,
    fix_rule_module,
    awareness_rule_module,
    packaging_rule_module,
    selection_rule_module,
]


class ValidationService:
    def __init__(
        self,
        selection_rules: dict,
        archive_pairs: list[list[str]],
        status_marker_service: StatusMarkerService,
        reference_element_service: ReferenceElementService | None = None,
    ) -> None:
        self.selection_rules = selection_rules
        self.archive_pairs = archive_pairs
        self.status_marker_service = status_marker_service
        self.reference_element_service = reference_element_service
        self.rule_modules = self._resolve_rule_modules()
        self.rule_definitions = tuple(
            rule_module.RULE for rule_module in self.rule_modules
        )

    def _resolve_rule_modules(
        self,
    ) -> tuple[RuleModule, ...]:
        return resolve_rule_modules(VALIDATION_RULE_MODULES)

    def get_rule_registry_rows(
        self,
    ) -> list[dict[str, str]]:
        return build_rule_registry_rows(self.rule_definitions)

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
        skip_location_validation_effort_ids: set[str] | None = None,
    ) -> tuple[list[Element], list[InventoryIssue]]:
        context = self._build_context(
            elements=elements,
            all_release_elements=all_release_elements,
            release_efforts=release_efforts,
            effort_release_lookup=effort_release_lookup,
            location_service=location_service,
            mode=mode,
            release=release,
            skip_location_validation_effort_ids=(
                skip_location_validation_effort_ids or set()
            ),
        )

        for rule_module in self.rule_modules:
            if skip_location_validation and rule_module.RULE.name == "location":
                continue

            rule_module.apply(context)

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
        skip_location_validation_effort_ids: set[str] | None = None,
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
            skip_location_validation_effort_ids=(
                skip_location_validation_effort_ids or set()
            ),
            location_service=location_service,
            reference_element_service=self.reference_element_service,
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
        skip_location_validation_effort_ids: set[str] | None = None,
    ) -> None:
        location_rule_module.apply(
            self._build_context(
                elements=elements,
                location_service=location_service,
                mode=mode,
                skip_location_validation_effort_ids=(
                    skip_location_validation_effort_ids or set()
                ),
            ),
        )

    def apply_archive_status(
        self,
        elements: list[Element],
        location_service: MainframeLocationService | None,
        mode: str,
        all_release_elements: list[Element] | None = None,
    ) -> None:
        archive_rule_module.apply(
            self._build_context(
                elements=elements,
                all_release_elements=all_release_elements,
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

