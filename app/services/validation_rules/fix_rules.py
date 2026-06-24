from __future__ import annotations

from app.core.models import FixStatus
from app.core.status_messages import ReasonBuilder
from app.services.validation_rules.base import ValidatorContext


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
