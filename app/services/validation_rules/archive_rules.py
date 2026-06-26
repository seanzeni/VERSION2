from __future__ import annotations

"""
Purpose:
    Apply archive/program counterpart validation for PROD moves.

Annotations:
    Uses postponed annotations for consistent validation rule typing.

Used By:
    ValidationService.apply_archive_status

Responsibilities:
    - Detect potential missing archive rows when a program counterpart exists.
    - Detect potential missing program moves when an archive row is present.
    - Use configured archive/program type pairs from ValidatorContext.
    - Skip archive warnings for elements marked DO NOT MOVE.

Notes:
    This module only runs archive checks for PROD because archive movement is
    suppressed for normal QUAL processing.
"""

from app.core.models import ArchiveStatus
from app.core.models import Element
from app.core.models import MovementStatus
from app.core.models import Severity
from app.core.status_messages import ReasonBuilder
from app.services.validation_rules import selection_rules
from app.services.validation_rules.base import RuleDefinition
from app.services.validation_rules.base import RulePhase
from app.services.validation_rules.base import ValidatorContext


RULE = RuleDefinition(
    name="archive",
    phase=RulePhase.ARCHIVE,
    dependencies=("movement", "schedule", "location"),
    description="Detect missing archive/program counterpart moves.",
)


def apply(
    context: ValidatorContext,
) -> None:
    if context.mode.upper() != "PROD":
        return

    location_service = context.location_service

    if location_service is None:
        return

    selected_inventory_lookup = {
        element.key: element
        for element in context.elements
    }
    full_inventory_lookup = {
        element.key: element
        for element in (context.all_release_elements or context.elements)
    }

    for element in context.elements:
        if element.movement_status == MovementStatus.DO_NOT_MOVE:
            continue

        element_name = element.element.strip().upper()
        element_type = element.type.strip().upper()

        opposite_type = get_opposite_type(
            type_name=element_type,
            archive_pairs=context.archive_pairs,
        )

        if opposite_type is None:
            continue

        if location_service.exists_in_env(
            element=element_name,
            type_=opposite_type,
            env="PROD1",
        ):
            counterpart_status = get_counterpart_inventory_status(
                element_name=element_name,
                type_name=opposite_type,
                selected_inventory_lookup=selected_inventory_lookup,
                full_inventory_lookup=full_inventory_lookup,
            )

            if counterpart_status.should_warn:
                element.archive_status = ArchiveStatus.POTENTIAL_MISSING_ARCHIVE

                context.add_reason(
                    element=element,
                    reason=ReasonBuilder.potential_missing_archive(
                        element=element.element,
                        moving_type=element.type,
                        opposite_type=opposite_type,
                        env="PROD1",
                        inventory_detail=counterpart_status.reason_detail,
                    ),
                )

        program_type = get_program_type_for_archive(
            archive_type=element_type,
            archive_pairs=context.archive_pairs,
        )

        if program_type is None or not selection_rules.is_archive_move(element):
            continue

        counterpart_status = get_counterpart_inventory_status(
            element_name=element_name,
            type_name=program_type,
            selected_inventory_lookup=selected_inventory_lookup,
            full_inventory_lookup=full_inventory_lookup,
        )

        if not counterpart_status.should_warn:
            continue

        found_env = (
            "QUAL1"
            if location_service.exists_in_env(
                element=element_name,
                type_=program_type,
                env="QUAL1",
            )
            else ""
        )

        element.archive_status = ArchiveStatus.POTENTIAL_MISSING_PROGRAM_MOVE

        context.add_reason(
            element=element,
            reason=ReasonBuilder.potential_missing_program_move(
                element=element.element,
                archive_type=element.type,
                program_type=program_type,
                env=found_env,
                inventory_detail=counterpart_status.reason_detail,
            ),
        )


def get_opposite_type(
    type_name: str,
    archive_pairs: list[list[str]],
) -> str | None:
    clean_type = str(type_name).strip().upper()

    for pair in archive_pairs:
        if len(pair) != 2:
            continue

        archive_type = str(pair[0]).strip().upper()

        program_type = str(pair[1]).strip().upper()

        if clean_type == archive_type:
            return program_type

        if clean_type == program_type:
            return archive_type

    return None


class CounterpartInventoryStatus:
    def __init__(
        self,
        should_warn: bool,
        reason_detail: str = "",
    ) -> None:
        self.should_warn = should_warn
        self.reason_detail = reason_detail


def get_counterpart_inventory_status(
    element_name: str,
    type_name: str,
    selected_inventory_lookup: dict[tuple[str, str], Element],
    full_inventory_lookup: dict[tuple[str, str], Element],
) -> CounterpartInventoryStatus:
    key = (
        element_name.strip().upper(),
        type_name.strip().upper(),
    )
    selected_counterpart = selected_inventory_lookup.get(key)

    if selected_counterpart is not None:
        if has_blocking_counterpart_issue(selected_counterpart):
            return CounterpartInventoryStatus(
                should_warn=True,
                reason_detail=(
                    "is present in inventory but not selectable. "
                    "See Element related issues."
                ),
            )

        if not selected_counterpart.selected:
            return CounterpartInventoryStatus(
                should_warn=True,
                reason_detail="is present in inventory but not selected.",
            )

        return CounterpartInventoryStatus(
            should_warn=False,
        )

    if key in full_inventory_lookup:
        return CounterpartInventoryStatus(
            should_warn=True,
            reason_detail="is present in inventory but not selected.",
        )

    return CounterpartInventoryStatus(
        should_warn=True,
        reason_detail="is not present in inventory at all.",
    )


def has_blocking_counterpart_issue(
    element: Element,
) -> bool:
    return (
        not element.selectable
        or element.severity in {Severity.ERROR, Severity.WARNING}
    )


def get_program_type_for_archive(
    archive_type: str,
    archive_pairs: list[list[str]],
) -> str | None:
    clean_type = str(archive_type).strip().upper()

    for pair in archive_pairs:
        if len(pair) != 2:
            continue

        archive_side = str(pair[0]).strip().upper()

        program_side = str(pair[1]).strip().upper()

        if clean_type == archive_side:
            return program_side

    return None
