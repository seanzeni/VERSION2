from __future__ import annotations

"""
Purpose:
    Flag elements that already exist in the FIXP1 environment.

Annotations:
    Uses postponed annotations for consistent validation rule typing.

Used By:
    ValidationService.apply_fixp1_status

Responsibilities:
    - Run only during PROD validation.
    - Check the mainframe location service for FIXP1 matches.
    - Mark matching elements with EXISTS_IN_FIXP1 and add the reason.

Notes:
    FIXP1 is a warning-style validation separate from normal source location
    validation.
"""

from app.core.models import FixStatus
from app.core.status_messages import ReasonBuilder
from app.services.validation_rules.base import RuleDefinition
from app.services.validation_rules.base import RulePhase
from app.services.validation_rules.base import ValidatorContext


RULE = RuleDefinition(
    name="fixp1",
    phase=RulePhase.FIX,
    dependencies=("movement", "location"),
    description="Warn when element/type also exists in FIXP1.",
)


def apply(
    context: ValidatorContext,
) -> None:
    if context.mode.upper() != "PROD":
        return

    location_service = context.location_service

    if location_service is None:
        return

    for element in context.elements:
        if location_service.exists_in_fixp1(
            element=element.element,
            type_=element.type,
        ):
            element.fix_status = FixStatus.EXISTS_IN_FIXP1

            context.add_reason(
                element=element,
                reason=ReasonBuilder.exists_in_fixp1(
                    element=element.element,
                    type_=element.type,
                ),
            )
