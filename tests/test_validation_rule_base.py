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
from app.services.validation_rules.base import RuleDefinition
from app.services.validation_rules.base import RulePhase
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


def test_require_rule_module_accepts_apply_function() -> None:
    rule_module = require_rule_module(ValidRuleModule, "valid")

    assert rule_module is ValidRuleModule
    assert rule_module.apply(ValidatorContext()) is None


def test_require_rule_module_rejects_missing_rule_definition() -> None:
    with pytest.raises(TypeError):
        require_rule_module(MissingDefinitionRuleModule, "invalid")


def test_require_rule_module_rejects_missing_apply() -> None:
    with pytest.raises(TypeError):
        require_rule_module(MissingApplyRuleModule, "invalid")
