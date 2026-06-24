from __future__ import annotations

from app.core.models import Element
from app.core.models import MovementStatus
from app.core.status_messages import ReasonBuilder
from app.services.mainframe_location_service import MainframeLocationService
from app.services.status_marker_service import StatusMarkerService


def apply(
    elements: list[Element],
    location_service: MainframeLocationService | None,
    status_marker_service: StatusMarkerService,
    mode: str,
    add_reason,
) -> None:
    target_env = get_target_env(
        mode=mode,
    )

    for element in elements:
        if status_marker_service.is_do_not_move(
            element=element,
        ):
            element.movement_status = MovementStatus.DO_NOT_MOVE

            add_reason(
                element=element,
                reason=ReasonBuilder.do_not_move(
                    element=element.element,
                    type_=element.type,
                    marker_text="DO NOT MOVE",
                ),
            )

            continue

        if not status_marker_service.is_marked_for_target(
            element=element,
            mode=mode,
        ):
            continue

        if location_service is not None and location_service.exists_in_env(
            element=element.element,
            type_=element.type,
            env=target_env,
        ):
            element.source_row["_confirmed_already_in_target"] = True
            continue

        marker_text = status_marker_service.get_target_marker_text(
            element=element,
            mode=mode,
        )

        element.movement_status = MovementStatus.MARKED_ALREADY_THERE_BUT_MISSING

        add_reason(
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
