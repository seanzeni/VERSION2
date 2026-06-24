from __future__ import annotations

from app.core.models import ArchiveStatus
from app.core.models import Element
from app.core.models import InventoryStatus
from app.core.models import LocationStatus
from app.core.models import MovementStatus
from app.core.models import ScheduleStatus
from app.core.package_rules import is_archive_package
from app.services.validation_rules.base import ValidatorContext


def apply(
    context: ValidatorContext,
) -> None:
    selection_rules = context.selection_rules

    for element in context.elements:
        element.selected = True
        element.selectable = True

        if (
            is_archive_type_for_qual_move(
                mode=context.mode,
                element=element,
                selection_rules=context.selection_rules,
            )
            and element.schedule_status == ScheduleStatus.OK
        ):
            element.selected = False
            element.selectable = False
            element.visible = False
            continue

        if element.inventory_status == InventoryStatus.OVERLAP:
            element.selected = False
            element.selectable = bool(
                selection_rules.get(
                    "overlap_selectable",
                    False,
                )
            )

        if element.inventory_status == InventoryStatus.DUPLICATE:
            element.selected = False
            element.selectable = bool(
                selection_rules.get(
                    "duplicate_selectable",
                    False,
                )
            )

        if element.schedule_status == ScheduleStatus.INVENTORY_NOT_IN_RELEASE:
            element.selected = False
            element.selectable = bool(
                selection_rules.get(
                    "inventory_not_in_release_selectable",
                    True,
                )
            )

        if element.schedule_status == ScheduleStatus.INVENTORY_WHEN_SQL_NO_INVENTORY:
            element.selected = False
            element.selectable = bool(
                selection_rules.get(
                    "inventory_when_sql_no_inventory_selectable",
                    True,
                )
            )

        if element.schedule_status == ScheduleStatus.EFFORT_RELEASE_MISMATCH:
            element.selected = False
            element.selectable = bool(
                selection_rules.get(
                    "effort_release_mismatch_selectable",
                    True,
                )
            )

        if element.archive_status == ArchiveStatus.POTENTIAL_MISSING_ARCHIVE:
            element.selected = False
            element.selectable = bool(
                selection_rules.get(
                    "potential_missing_archive_selectable",
                    False,
                )
            )

        if element.archive_status == ArchiveStatus.POTENTIAL_MISSING_PROGRAM_MOVE:
            element.selected = False
            element.selectable = bool(
                selection_rules.get(
                    "potential_missing_program_move_selectable",
                    True,
                )
            )

        if element.movement_status == MovementStatus.DO_NOT_MOVE:
            element.selected = False
            element.selectable = bool(
                selection_rules.get(
                    "do_not_move_selectable",
                    False,
                )
            )

        if element.movement_status == MovementStatus.MARKED_ALREADY_THERE_BUT_MISSING:
            element.selected = False
            element.selectable = bool(
                selection_rules.get(
                    "marked_already_there_missing_selectable",
                    True,
                )
            )

        if (
            is_confirmed_already_in_target(element)
            and element.schedule_status == ScheduleStatus.OK
        ):
            element.selected = False
            element.selectable = False
            element.visible = False

        if element.location_status == LocationStatus.NOT_FOUND:
            element.selected = False
            element.selectable = bool(
                selection_rules.get(
                    "missing_ndvr_selectable",
                    False,
                )
            )


def is_confirmed_already_in_target(
    element: Element,
) -> bool:
    return bool(
        element.source_row.get(
            "_confirmed_already_in_target",
            False,
        )
    )


def is_archive_type_for_qual_move(
    mode: str,
    element: Element,
    selection_rules: dict,
) -> bool:
    return (
        mode.upper() == "QUAL"
        and bool(
            selection_rules.get(
                "hide_archive_rows_in_qual",
                True,
            )
        )
        and is_archive_move(element)
    )


def is_archive_move(
    element: Element,
) -> bool:
    package_value = element.source_row.get(
        "Package",
        "",
    )

    return is_archive_package(package_value)
