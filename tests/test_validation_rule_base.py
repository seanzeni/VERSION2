from __future__ import annotations

import pytest

from app.services.validation_rules.base import require_rule_module


class ValidRuleModule:
    @staticmethod
    def apply() -> None:
        return None


class InvalidRuleModule:
    pass


def test_require_rule_module_accepts_apply_function() -> None:
    assert require_rule_module(ValidRuleModule, "valid") is ValidRuleModule


def test_require_rule_module_rejects_missing_apply() -> None:
    with pytest.raises(TypeError):
        require_rule_module(InvalidRuleModule, "invalid")
