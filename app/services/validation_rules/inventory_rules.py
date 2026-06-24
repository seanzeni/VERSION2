from __future__ import annotations

from collections import defaultdict

from app.core.models import Element
from app.core.models import InventoryStatus
from app.core.models import MovementStatus
from app.core.status_messages import ReasonBuilder
from app.services.validation_rules.base import ValidatorContext


def apply(
    context: ValidatorContext,
) -> None:
    grouped: dict[tuple[str, str], list[Element]] = defaultdict(list)

    for element in context.elements:
        if element.movement_status != MovementStatus.DO_NOT_MOVE:
            grouped[element.key].append(element)

    for group in grouped.values():
        projects = {element.project for element in group}
        project_counts: dict[str, int] = defaultdict(int)

        for element in group:
            project_counts[element.project] += 1

        if len(projects) > 1:
            for element in group:
                element.inventory_status = InventoryStatus.OVERLAP

                context.add_reason(
                    element=element,
                    reason=ReasonBuilder.overlap(
                        element=element.element,
                        type_=element.type,
                        project=element.project,
                        other_projects=sorted(
                            project
                            for project in projects
                            if project != element.project
                        ),
                    ),
                )

                if project_counts[element.project] > 1:
                    context.add_reason(
                        element=element,
                        reason=ReasonBuilder.duplicate(
                            element=element.element,
                            type_=element.type,
                            project=element.project,
                        ),
                    )

        elif len(group) > 1:
            for element in group:
                element.inventory_status = InventoryStatus.DUPLICATE

                context.add_reason(
                    element=element,
                    reason=ReasonBuilder.duplicate(
                        element=element.element,
                        type_=element.type,
                        project=element.project,
                    ),
                )
