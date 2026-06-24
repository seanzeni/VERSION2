from __future__ import annotations

import pytest

from app.services.validation_rules.base import require_rule_module
from app.services.validation_rules.base import ValidatorContext


class ValidRuleModule:
    @staticmethod
    def apply(
        context: ValidatorContext,
    ) -> None:
        return None


class InvalidRuleModule:
    pass


def test_require_rule_module_accepts_apply_function() -> None:
    rule_module = require_rule_module(ValidRuleModule, "valid")

    assert rule_module is ValidRuleModule
    assert rule_module.apply(ValidatorContext()) is None


def test_require_rule_module_rejects_missing_apply() -> None:
    with pytest.raises(TypeError):
        require_rule_module(InvalidRuleModule, "invalid")
