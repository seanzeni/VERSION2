from __future__ import annotations

# Purpose:
#     Block PROD rows whose loaded NDVR return code can break packaging.

from app.core.models import PackagingStatus
from app.core.status_messages import ReasonBuilder
from app.services.validation_rules import location_rules
from app.services.validation_rules import selection_rules
from app.services.validation_rules.base import RuleDefinition
from app.services.validation_rules.base import RulePhase
from app.services.validation_rules.base import ValidatorContext


DEFAULT_MAX_NDVR_RC = 8


RULE = RuleDefinition(
    name="packaging",
    phase=RulePhase.PACKAGING,
    dependencies=("location",),
    description="Block non-archive PROD rows when the expected source location has an RC above the threshold.",
)


def apply(
    context: ValidatorContext,
) -> None:
    location_service = context.location_service

    if location_service is None:
        return

    if context.mode.upper() != "PROD":
        return

    threshold = int(
        context.selection_rules.get(
            "ndvr_rc_max_allowed",
            DEFAULT_MAX_NDVR_RC,
        )
    )

    for element in context.elements:
        if selection_rules.is_archive_move(element):
            continue

        expected_env = location_rules.get_source_env_for_move(
            mode=context.mode,
            element=element,
        )
        expected_system = location_rules.get_expected_system_for_move(
            mode=context.mode,
            element=element,
        )
        expected_subsystem = location_rules.get_expected_subsystem_for_move(
            mode=context.mode,
            element=element,
        )

        bad_records = [
            record
            for record in location_service.find(
                element.element,
                element.type,
            )
            if record.env.strip().upper() == expected_env
            and record.system.strip().upper() == expected_system
            and record.subsystem.strip().upper() == expected_subsystem
            and record.ndvr_rc is not None
            and record.ndvr_rc > threshold
        ]

        if not bad_records:
            continue

        worst_record = max(
            bad_records,
            key=lambda record: record.ndvr_rc or 0,
        )
        element.packaging_status = PackagingStatus.NDVR_RC_TOO_HIGH
        context.add_reason(
            element=element,
            reason=ReasonBuilder.ndvr_rc_too_high(
                element=element.element,
                type_=element.type,
                ndvr_rc=worst_record.ndvr_rc or 0,
                threshold=threshold,
            ),
        )
