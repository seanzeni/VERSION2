from __future__ import annotations

# Purpose:
#     Apply movement marker validation from package/source row text.
#
# Annotations:
#     Uses postponed annotations for consistent validation rule typing.
#
# Used By:
#     ValidationService.apply_movement_status
#     ValidationService.get_target_env
#
# Responsibilities:
#     - Mark rows as DO NOT MOVE when configured marker text is present.
#     - Confirm rows marked already in target are actually in the target env.
#     - Flag rows marked already there but missing from the target env.
#     - Store confirmed target matches for selection filtering.
#
# Notes:
#     This rule runs before location and selection validation because later rules
#     depend on movement status.

from app.core.models import MovementStatus
from app.core.status_messages import ReasonBuilder
from app.services.validation_rules.base import RuleDefinition
from app.services.validation_rules.base import RulePhase
from app.services.validation_rules.base import ValidatorContext


RULE = RuleDefinition(
    name="movement",
    phase=RulePhase.MOVEMENT,
    dependencies=(),
    description="Apply movement marker rules before other validation phases.",
)


def apply(
    context: ValidatorContext,
) -> None:
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

        marked_environments = context.status_marker_service.get_marked_environments(
            element
        )

        if not marked_environments:
            continue

        found_marker_status: MovementStatus | None = None
        missing_marked_location = False

        for marked_env, marker_text in marked_environments:
            if context.location_service is not None and context.location_service.exists_in_env(
                element=element.element,
                type_=element.type,
                env=marked_env,
            ):
                element.source_row["_confirmed_already_in_target"] = True
                element.source_row.setdefault(
                    "_confirmed_marked_envs",
                    [],
                ).append(marked_env)
                element.movement_status = get_confirmed_marker_status(marked_env)
                context.add_reason(
                    element=element,
                    reason=ReasonBuilder.marked_already_there_confirmed(
                        element=element.element,
                        type_=element.type,
                        target_env=marked_env,
                        marker_text=marker_text,
                    ),
                )
                found_marker_status = found_marker_status or get_confirmed_marker_status(
                    marked_env
                )
                continue

            missing_marked_location = True

            context.add_reason(
                element=element,
                reason=ReasonBuilder.marked_already_there_but_missing(
                    element=element.element,
                    type_=element.type,
                    target_env=marked_env,
                    marker_text=marker_text,
                ),
            )

        if missing_marked_location:
            element.movement_status = MovementStatus.MARKED_ALREADY_THERE_BUT_MISSING
        elif found_marker_status is not None:
            element.movement_status = found_marker_status


def get_target_env(
    mode: str,
) -> str:
    if mode.upper() == "PROD":
        return "PROD1"

    return "QUAL1"


def get_confirmed_marker_status(
    env: str,
) -> MovementStatus:
    if env.upper() == "PROD1":
        return MovementStatus.MARKED_IN_PROD

    if env.upper() == "QUAL1":
        return MovementStatus.MARKED_IN_QUAL

    return MovementStatus.OK
