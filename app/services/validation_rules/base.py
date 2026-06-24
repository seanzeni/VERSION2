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
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field
from typing import Protocol

from app.core.models import Element
from app.core.models import ReleaseEffort
from app.services.mainframe_location_service import MainframeLocationService
from app.services.status_marker_service import StatusMarkerService


AddReason = Callable[[Element, str], None]


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
    location_service: MainframeLocationService | None = None
    status_marker_service: StatusMarkerService | None = None
    add_reason: AddReason = _noop_add_reason


class ValidationRule(ABC):
    name: str

    @abstractmethod
    def apply(
        self,
        context: ValidatorContext,
    ) -> None:
        raise NotImplementedError


class RuleModule(Protocol):
    def apply(
        self,
        context: ValidatorContext,
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
