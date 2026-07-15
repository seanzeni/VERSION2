from __future__ import annotations

# Purpose:
#     Define the shared validation rule contract and execution context.
#
# Annotations:
#     Uses postponed annotations so rule context type hints can reference
#     application models without runtime ordering issues.
#
# Used By:
#     ValidationService
#     validation rule modules
#     validation rule tests
#
# Responsibilities:
#     - Carry shared validation inputs through ValidatorContext.
#     - Define the ValidationRule abstract class for class-based rules.
#     - Define the RuleModule protocol for module-based rules.
#     - Validate that rule modules expose an apply(context) entry point.
#
# Notes:
#     Current rules are module-level functions. ValidationRule is available
#     when a rule grows enough behavior to justify a class.

from abc import ABC
from abc import abstractmethod
from collections.abc import Callable
from collections.abc import Iterable
from dataclasses import dataclass
from dataclasses import field
from enum import Enum
from typing import Protocol

from app.core.models import Element
from app.core.models import ReleaseEffort
from app.services.mainframe_location_service import MainframeLocationService
from app.services.reference_element_service import ReferenceElementService
from app.services.status_marker_service import StatusMarkerService


AddReason = Callable[[Element, str], None]


class RulePhase(str, Enum):
    MOVEMENT = "movement"
    INVENTORY = "inventory"
    SCHEDULE = "schedule"
    LOCATION = "location"
    ARCHIVE = "archive"
    FIX = "fix"
    AWARENESS = "awareness"
    PACKAGING = "packaging"
    SELECTION = "selection"


RULE_PHASE_ORDER = {
    phase: order
    for order, phase in enumerate(
        RulePhase,
        start=1,
    )
}


@dataclass(frozen=True, slots=True)
class RuleDefinition:
    name: str
    phase: RulePhase
    dependencies: tuple[str, ...] = ()
    description: str = ""


def _noop_add_reason(
    element: Element,
    reason: str,
) -> None:
    return None


@dataclass(slots=True)
class ValidatorContext:
    elements: list[Element] = field(default_factory=list)
    all_release_elements: list[Element] = field(default_factory=list)
    release_efforts: list[ReleaseEffort] = field(default_factory=list)
    effort_release_lookup: dict[str, str] = field(default_factory=dict)
    release: str = ""
    mode: str = ""
    selection_rules: dict = field(default_factory=dict)
    archive_pairs: list[list[str]] = field(default_factory=list)
    skip_location_validation_effort_ids: set[str] = field(default_factory=set)
    location_service: MainframeLocationService | None = None
    reference_element_service: ReferenceElementService | None = None
    status_marker_service: StatusMarkerService | None = None
    add_reason: AddReason = _noop_add_reason


class ValidationRule(ABC):
    definition: RuleDefinition

    @abstractmethod
    def apply(
        self,
        context: ValidatorContext,
    ) -> None:
        raise NotImplementedError


class RuleModule(Protocol):
    RULE: RuleDefinition

    def apply(
        self,
        context: ValidatorContext,
    ) -> None:
        ...


def require_rule_module(
    rule_module: object,
    rule_name: str,
) -> RuleModule:
    definition = getattr(
        rule_module,
        "RULE",
        None,
    )

    if not isinstance(definition, RuleDefinition):
        raise TypeError(
            f"Validation rule module {rule_name!r} must define a RULE RuleDefinition."
        )

    if not definition.name:
        raise TypeError(
            f"Validation rule module {rule_name!r} must define a non-empty rule name."
        )

    apply_function = getattr(
        rule_module,
        "apply",
        None,
    )

    if not callable(apply_function):
        raise TypeError(
            f"Validation rule module {rule_name!r} must define an apply() function."
        )

    return rule_module


def validate_rule_modules(
    rule_modules: Iterable[object],
) -> tuple[RuleDefinition, ...]:
    return tuple(
        rule_module.RULE for rule_module in resolve_rule_modules(rule_modules)
    )


def resolve_rule_modules(
    rule_modules: Iterable[object],
) -> tuple[RuleModule, ...]:
    validated_modules: list[RuleModule] = []
    original_order: dict[str, int] = {}
    rules_by_name: dict[str, RuleDefinition] = {}

    for index, rule_module in enumerate(rule_modules):
        rule_name = getattr(
            rule_module,
            "__name__",
            rule_module.__class__.__name__,
        )
        validated_module = require_rule_module(
            rule_module=rule_module,
            rule_name=rule_name,
        )
        rule = validated_module.RULE

        if rule.name in rules_by_name:
            raise TypeError(f"Duplicate validation rule name: {rule.name}")

        validated_modules.append(validated_module)
        original_order[rule.name] = index
        rules_by_name[rule.name] = rule

    for rule in rules_by_name.values():
        missing_dependencies = [
            dependency
            for dependency in rule.dependencies
            if dependency not in rules_by_name
        ]

        if missing_dependencies:
            raise TypeError(
                f"Validation rule {rule.name!r} depends on unknown rules: "
                + ", ".join(missing_dependencies)
            )

    remaining = {
        rule_module.RULE.name: rule_module
        for rule_module in validated_modules
    }
    resolved_names: set[str] = set()
    resolved_modules: list[RuleModule] = []

    while remaining:
        ready_modules = [
            rule_module
            for rule_module in remaining.values()
            if all(
                dependency in resolved_names
                for dependency in rule_module.RULE.dependencies
            )
        ]

        if not ready_modules:
            cycle_names = ", ".join(sorted(remaining.keys()))
            raise TypeError(
                "Validation rule dependencies contain a cycle involving: "
                + cycle_names
            )

        ready_modules.sort(
            key=lambda rule_module: (
                RULE_PHASE_ORDER[rule_module.RULE.phase],
                original_order[rule_module.RULE.name],
                rule_module.RULE.name,
            )
        )
        selected_module = ready_modules[0]

        resolved_modules.append(selected_module)
        resolved_names.add(selected_module.RULE.name)
        del remaining[selected_module.RULE.name]

    return tuple(resolved_modules)


def build_rule_registry_rows(
    definitions: Iterable[RuleDefinition],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    for order, definition in enumerate(
        definitions,
        start=1,
    ):
        rows.append(
            {
                "order": str(order),
                "name": definition.name,
                "phase": definition.phase.value,
                "dependencies": ", ".join(definition.dependencies) or "None",
                "description": definition.description,
            }
        )

    return rows
