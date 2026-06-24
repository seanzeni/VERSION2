from __future__ import annotations

"""
Purpose:
    Shared contract helpers for validation rules.

Notes:
    Current validation rules are module-level functions because each rule
    needs a slightly different set of inputs. ValidationRule is available
    for future class-based rules, while require_rule_module protects the
    current module-style convention at startup.
"""

from abc import ABC
from abc import abstractmethod
from typing import Any
from typing import Protocol


class ValidationRule(ABC):
    name: str

    @abstractmethod
    def apply(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        raise NotImplementedError


class RuleModule(Protocol):
    def apply(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        ...


def require_rule_module(
    rule_module: object,
    rule_name: str,
) -> RuleModule:
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
