from __future__ import annotations

from app.core.models import Element
from app.core.models import FixStatus
from app.core.status_messages import ReasonBuilder
from app.services.mainframe_location_service import MainframeLocationService


def apply(
    elements: list[Element],
    location_service: MainframeLocationService | None,
    mode: str,
    add_reason,
) -> None:
    if mode.upper() != "PROD":
        return

    if location_service is None:
        return

    for element in elements:
        if location_service.exists_in_fixp1(
            element=element.element,
            type_=element.type,
        ):
            element.fix_status = FixStatus.EXISTS_IN_FIXP1

            add_reason(
                element=element,
                reason=ReasonBuilder.exists_in_fixp1(
                    element=element.element,
                    type_=element.type,
                ),
            )
