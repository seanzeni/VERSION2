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
from app.core.models import MovementStatus
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

    inventory_lookup = {element.key for element in context.elements}

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
            if (
                element_name,
                opposite_type,
            ) not in inventory_lookup:
                element.archive_status = ArchiveStatus.POTENTIAL_MISSING_ARCHIVE

                context.add_reason(
                    element=element,
                    reason=ReasonBuilder.potential_missing_archive(
                        element=element.element,
                        moving_type=element.type,
                        opposite_type=opposite_type,
                        env="PROD1",
                    ),
                )

        program_type = get_program_type_for_archive(
            archive_type=element_type,
            archive_pairs=context.archive_pairs,
        )

        if program_type is None or not selection_rules.is_archive_move(element):
            continue

        if (
            element_name,
            program_type,
        ) in inventory_lookup:
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
