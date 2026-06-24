from __future__ import annotations

"""
Purpose:
    Apply movement marker validation from package/source row text.

Annotations:
    Uses postponed annotations for consistent validation rule typing.

Used By:
    ValidationService.apply_movement_status
    ValidationService.get_target_env

Responsibilities:
    - Mark rows as DO NOT MOVE when configured marker text is present.
    - Confirm rows marked already in target are actually in the target env.
    - Flag rows marked already there but missing from the target env.
    - Store confirmed target matches for selection filtering.

Notes:
    This rule runs before location and selection validation because later rules
    depend on movement status.
"""

from app.core.models import MovementStatus
from app.core.status_messages import ReasonBuilder
from app.services.validation_rules.base import ValidatorContext


def apply(
    context: ValidatorContext,
) -> None:
    target_env = get_target_env(
        mode=context.mode,
    )

    if context.status_marker_service is None:
        return

    for element in context.elements:
        if context.status_marker_service.is_do_not_move(
            element=element,
        ):
            element.movement_status = MovementStatus.DO_NOT_MOVE

            context.add_reason(
                element=element,
                reason=ReasonBuilder.do_not_move(
                    element=element.element,
                    type_=element.type,
                    marker_text="DO NOT MOVE",
                ),
            )

            continue

        if not context.status_marker_service.is_marked_for_target(
            element=element,
            mode=context.mode,
        ):
            continue

        if context.location_service is not None and context.location_service.exists_in_env(
            element=element.element,
            type_=element.type,
            env=target_env,
        ):
            element.source_row["_confirmed_already_in_target"] = True
            continue

        marker_text = context.status_marker_service.get_target_marker_text(
            element=element,
            mode=context.mode,
        )

        element.movement_status = MovementStatus.MARKED_ALREADY_THERE_BUT_MISSING

        context.add_reason(
            element=element,
            reason=ReasonBuilder.marked_already_there_but_missing(
                element=element.element,
                type_=element.type,
                target_env=target_env,
                marker_text=marker_text,
            ),
        )


def get_target_env(
    mode: str,
) -> str:
    if mode.upper() == "PROD":
        return "PROD1"

    return "QUAL1"
