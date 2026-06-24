from __future__ import annotations

from app.core.models import ArchiveStatus
from app.core.models import Element
from app.core.models import MovementStatus
from app.core.status_messages import ReasonBuilder
from app.services.mainframe_location_service import MainframeLocationService
from app.services.validation_rules import selection_rules


def apply(
    elements: list[Element],
    location_service: MainframeLocationService | None,
    mode: str,
    archive_pairs: list[list[str]],
    add_reason,
) -> None:
    if mode.upper() != "PROD":
        return

    if location_service is None:
        return

    inventory_lookup = {element.key for element in elements}

    for element in elements:
        if element.movement_status == MovementStatus.DO_NOT_MOVE:
            continue

        element_name = element.element.strip().upper()
        element_type = element.type.strip().upper()

        opposite_type = get_opposite_type(
            type_name=element_type,
            archive_pairs=archive_pairs,
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

                add_reason(
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
            archive_pairs=archive_pairs,
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

        add_reason(
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
