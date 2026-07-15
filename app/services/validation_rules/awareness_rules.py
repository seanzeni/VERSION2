from __future__ import annotations

# Purpose:
#     Add informational awareness flags for configured reference lists.

from app.core.models import AwarenessStatus
from app.core.status_messages import ReasonBuilder
from app.services.validation_rules.base import RuleDefinition
from app.services.validation_rules.base import RulePhase
from app.services.validation_rules.base import ValidatorContext


RULE = RuleDefinition(
    name="awareness",
    phase=RulePhase.AWARENESS,
    dependencies=("schedule",),
    description="Flag HIPPA listener and ODS reference-list matches as informational.",
)


def apply(
    context: ValidatorContext,
) -> None:
    reference_service = context.reference_element_service

    if reference_service is None:
        return

    for element in context.elements:
        hippa_row = reference_service.get(
            "hippa_listener",
            element.element,
            element.type,
        )
        ods_row = reference_service.get(
            "ods",
            element.element,
            element.type,
        )

        if hippa_row and ods_row:
            element.awareness_status = AwarenessStatus.HIPPA_LISTENER_AND_ODS_ELEMENT
        elif hippa_row:
            element.awareness_status = AwarenessStatus.HIPPA_LISTENER
        elif ods_row:
            element.awareness_status = AwarenessStatus.ODS_ELEMENT

        if hippa_row:
            context.add_reason(
                element=element,
                reason=ReasonBuilder.hippa_listener(
                    element=element.element,
                    type_=element.type,
                    listener=hippa_row.get("Listener", ""),
                    listener_transactions=hippa_row.get(
                        "Listener Transactions",
                        "",
                    ),
                ),
            )

        if ods_row:
            context.add_reason(
                element=element,
                reason=ReasonBuilder.ods_element(
                    element=element.element,
                    type_=element.type,
                ),
            )
