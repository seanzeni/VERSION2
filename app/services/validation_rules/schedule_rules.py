from __future__ import annotations

from app.core.models import Element
from app.core.models import InventoryIssue
from app.core.models import ReleaseEffort
from app.core.models import ScheduleStatus
from app.core.status_messages import ReasonBuilder


def apply(
    elements: list[Element],
    release_efforts: list[ReleaseEffort],
    effort_release_lookup: dict[str, str],
    release: str,
    add_reason,
) -> None:
    release_effort_ids = {
        effort.effort_id.strip()
        for effort in release_efforts
        if effort.effort_id.strip()
    }

    no_inventory_effort_ids = {
        effort.effort_id.strip()
        for effort in release_efforts
        if effort.no_inventory and effort.effort_id.strip()
    }

    for element in elements:
        effort_id = element.project.strip()
        sql_release = effort_release_lookup.get(
            effort_id,
        )

        if sql_release and sql_release.upper() != element.release.upper():
            element.schedule_status = ScheduleStatus.EFFORT_RELEASE_MISMATCH

            add_reason(
                element=element,
                reason=ReasonBuilder.effort_release_mismatch(
                    project=element.project,
                    inventory_release=element.release,
                    sql_release=sql_release,
                ),
            )

            continue

        if effort_id in no_inventory_effort_ids:
            element.schedule_status = ScheduleStatus.INVENTORY_WHEN_SQL_NO_INVENTORY

            add_reason(
                element=element,
                reason=ReasonBuilder.inventory_when_sql_no_inventory(
                    project=element.project,
                    release=release,
                ),
            )

            continue

        if effort_id not in release_effort_ids:
            element.schedule_status = ScheduleStatus.INVENTORY_NOT_IN_RELEASE

            add_reason(
                element=element,
                reason=ReasonBuilder.inventory_not_in_release(
                    project=element.project,
                    release=release,
                ),
            )


def build_inventory_issues(
    release: str,
    all_release_elements: list[Element],
    release_efforts: list[ReleaseEffort],
) -> list[InventoryIssue]:
    inventory_effort_ids = {
        element.project.strip()
        for element in all_release_elements
        if element.project.strip()
    }

    issues: list[InventoryIssue] = []

    for effort in release_efforts:
        effort_id = effort.effort_id.strip()

        if not effort_id:
            continue

        if effort.no_inventory:
            continue

        if effort_id not in inventory_effort_ids:
            issues.append(
                InventoryIssue(
                    release=release,
                    effort_id=effort_id,
                    issue_type=ScheduleStatus.SQL_EXPECTED_INVENTORY_MISSING,
                    reason=ReasonBuilder.sql_expected_inventory_missing(
                        project=effort_id,
                        release=release,
                    ),
                    expected_release=release,
                    inventory_release="",
                )
            )

    return issues
