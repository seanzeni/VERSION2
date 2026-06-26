from __future__ import annotations

"""
Purpose:
    Verify validation rule contract helpers.

Annotations:
    Uses postponed annotations to match the validation rule modules.

Used By:
    pytest

Responsibilities:
    - Confirm valid rule modules are accepted.
    - Confirm modules without apply(context) are rejected.
    - Confirm accepted modules can be invoked with ValidatorContext.

Notes:
    These tests protect the startup guard used by ValidationService.
"""

import pytest

from app.services.validation_rules.base import require_rule_module
from app.services.validation_rules.base import build_rule_registry_rows
from app.services.validation_rules.base import resolve_rule_modules
from app.services.validation_rules.base import RuleDefinition
from app.services.validation_rules.base import RulePhase
from app.services.validation_rules.base import validate_rule_modules
from app.services.validation_rules.base import ValidatorContext


class ValidRuleModule:
    RULE = RuleDefinition(
        name="valid",
        phase=RulePhase.MOVEMENT,
    )

    @staticmethod
    def apply(
        context: ValidatorContext,
    ) -> None:
        return None


class MissingApplyRuleModule:
    RULE = RuleDefinition(
        name="invalid",
        phase=RulePhase.MOVEMENT,
    )


class MissingDefinitionRuleModule:
    pass


class DependencyRuleModule:
    RULE = RuleDefinition(
        name="dependent",
        phase=RulePhase.SCHEDULE,
        dependencies=("valid",),
        description="Depends on a prior rule.",
    )

    @staticmethod
    def apply(
        context: ValidatorContext,
    ) -> None:
        return None


class DuplicateRuleModule:
    RULE = RuleDefinition(
        name="valid",
        phase=RulePhase.INVENTORY,
    )

    @staticmethod
    def apply(
        context: ValidatorContext,
    ) -> None:
        return None


class CycleStartRuleModule:
    RULE = RuleDefinition(
        name="cycle_start",
        phase=RulePhase.MOVEMENT,
        dependencies=("cycle_end",),
    )

    @staticmethod
    def apply(
        context: ValidatorContext,
    ) -> None:
        return None


class CycleEndRuleModule:
    RULE = RuleDefinition(
        name="cycle_end",
        phase=RulePhase.SELECTION,
        dependencies=("cycle_start",),
    )

    @staticmethod
    def apply(
        context: ValidatorContext,
    ) -> None:
        return None


def test_require_rule_module_accepts_apply_function() -> None:
    """Verifies require rule module accepts apply function."""
    rule_module = require_rule_module(ValidRuleModule, "valid")

    assert rule_module is ValidRuleModule
    assert rule_module.apply(ValidatorContext()) is None


def test_require_rule_module_rejects_missing_rule_definition() -> None:
    """Verifies require rule module rejects missing rule definition."""
    with pytest.raises(TypeError):
        require_rule_module(MissingDefinitionRuleModule, "invalid")


def test_require_rule_module_rejects_missing_apply() -> None:
    """Verifies require rule module rejects missing apply."""
    with pytest.raises(TypeError):
        require_rule_module(MissingApplyRuleModule, "invalid")


def test_validate_rule_modules_orders_dependencies() -> None:
    """Verifies validate rule modules orders dependencies."""
    definitions = validate_rule_modules([DependencyRuleModule, ValidRuleModule])

    assert [definition.name for definition in definitions] == ["valid", "dependent"]


def test_resolve_rule_modules_returns_modules_in_dependency_order() -> None:
    """Verifies resolve rule modules returns modules in dependency order."""
    rule_modules = resolve_rule_modules([DependencyRuleModule, ValidRuleModule])

    assert [rule_module.RULE.name for rule_module in rule_modules] == [
        "valid",
        "dependent",
    ]


def test_validate_rule_modules_rejects_duplicate_names() -> None:
    """Verifies validate rule modules rejects duplicate names."""
    with pytest.raises(TypeError):
        validate_rule_modules([ValidRuleModule, DuplicateRuleModule])


def test_validate_rule_modules_rejects_unknown_dependency() -> None:
    """Verifies validate rule modules rejects unknown dependency."""
    with pytest.raises(TypeError):
        validate_rule_modules([DependencyRuleModule])


def test_validate_rule_modules_rejects_dependency_cycle() -> None:
    """Verifies validate rule modules rejects dependency cycle."""
    with pytest.raises(TypeError):
        validate_rule_modules([CycleStartRuleModule, CycleEndRuleModule])


def test_build_rule_registry_rows_formats_dependencies() -> None:
    """Verifies build rule registry rows formats dependencies."""
    rows = build_rule_registry_rows(
        validate_rule_modules([ValidRuleModule, DependencyRuleModule])
    )

    assert rows[0]["order"] == "1"
    assert rows[0]["dependencies"] == "None"
    assert rows[1]["dependencies"] == "valid"
    assert rows[1]["description"] == "Depends on a prior rule."
