from __future__ import annotations

"""
Purpose:
    Validate that each movable element exists in its expected NDVR location.

Annotations:
    Uses postponed annotations for consistent validation rule typing.

Used By:
    ValidationService.apply_location_status
    ValidationService location helper methods

Responsibilities:
    - Determine expected source environment, system, and subsystem.
    - Confirm element/type presence in the expected mainframe location.
    - Record lower-environment locations when the expected location is missing.
    - Suppress QUAL archive rows that are intentionally hidden from movement.

Notes:
    PROD moves normally validate from QUAL1, except archive moves which validate
    from PROD1.
"""

from app.core.models import Element
from app.core.models import LocationStatus
from app.core.models import MovementStatus
from app.core.models import ScheduleStatus
from app.core.status_messages import ReasonBuilder
from app.services.mainframe_location_service import MainframeLocationService
from app.services.validation_rules import selection_rules
from app.services.validation_rules.base import ValidatorContext


def apply(
    context: ValidatorContext,
) -> None:
    location_service = context.location_service

    if location_service is None:
        return

    for element in context.elements:
        if element.movement_status == MovementStatus.DO_NOT_MOVE:
            continue

        if (
            selection_rules.is_archive_type_for_qual_move(
                mode=context.mode,
                element=element,
                selection_rules=context.selection_rules,
            )
            and element.schedule_status == ScheduleStatus.OK
        ):
            continue

        expected_env = get_source_env_for_move(
            mode=context.mode,
            element=element,
        )
        expected_system = get_expected_system_for_move(
            mode=context.mode,
            element=element,
        )
        expected_subsystem = get_expected_subsystem_for_move(
            mode=context.mode,
            element=element,
        )

        if location_service.exists_in_location(
            element=element.element,
            type_=element.type,
            env=expected_env,
            system=expected_system,
            subsystem=expected_subsystem,
        ):
            element.location_status = LocationStatus.FOUND
            continue

        expected_level = get_env_level(
            env=expected_env,
        )

        found_records = [
            record
            for record in location_service.find(
                element=element.element,
                type_=element.type,
            )
            if get_env_level(record.env) < expected_level
        ]
        found_locations = [
            f"{record.env} / {record.system} / {record.subsystem}"
            for record in found_records
        ]

        element.location_status = LocationStatus.NOT_FOUND

        context.add_reason(
            element=element,
            reason=ReasonBuilder.missing_ndvr(
                element=element.element,
                type_=element.type,
                expected_env=expected_env,
                expected_system=expected_system,
                expected_subsystem=expected_subsystem,
                found_locations=found_locations,
            ),
        )


def get_env_level(
    env: str,
) -> int:
    return MainframeLocationService.ENV_LEVELS.get(
        str(env).strip().upper(),
        0,
    )


def get_source_env_for_move(
    mode: str,
    element: Element,
) -> str:
    if mode.upper() == "PROD":
        if selection_rules.is_archive_move(element):
            return "PROD1"

        return "QUAL1"

    act_region = str(
        element.source_row.get(
            "Act Rgn",
            "",
        )
    ).strip().upper()

    if act_region.startswith("DV"):
        return "DEVL1"

    if act_region.startswith("LO"):
        return "MAIN1"

    return "QUAL1"


def get_expected_system_for_move(
    mode: str,
    element: Element,
) -> str:
    system_value = str(
        element.source_row.get(
            "System",
            "",
        )
    ).strip().upper()

    if mode.upper() == "PROD" and system_value:
        return system_value[:7] + "1"

    return system_value


def get_expected_subsystem_for_move(
    mode: str,
    element: Element,
) -> str:
    return str(
        element.source_row.get(
            "Subsys",
            "",
        )
    ).strip().upper()
