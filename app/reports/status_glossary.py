from __future__ import annotations

"""
Purpose:
    Maintain report column and status explanations.

Used By:
    IssuesReport
    Developer documentation

Responsibilities:
    - Define human-readable Issues Report column descriptions.
    - Define human-readable status meanings.
    - Keep report glossary output centralized for maintenance.

Notes:
    Update this file when adding report columns or status values.
"""

from app.core.models import ArchiveStatus
from app.core.models import FixStatus
from app.core.models import InventoryStatus
from app.core.models import LocationStatus
from app.core.models import MovementStatus
from app.core.models import ResyncStatus
from app.core.models import ScheduleStatus
from app.core.models import Severity
from app.reports.report_schemas import ISSUES_COLUMNS


STATUS_GROUPS = [
    ("Severity", Severity),
    ("Inventory Status", InventoryStatus),
    ("Schedule Status", ScheduleStatus),
    ("Location Status", LocationStatus),
    ("Archive Status", ArchiveStatus),
    ("Fix Status", FixStatus),
    ("Movement Status", MovementStatus),
    ("Resync Status", ResyncStatus),
]


def get_issues_glossary_rows() -> list[list[str]]:
    return [
        [
            "Column",
            column.name,
            "",
            "",
            column.description,
        ]
        for column in ISSUES_COLUMNS
    ] + get_status_glossary_rows()


def get_status_glossary_rows() -> list[list[str]]:
    rows: list[list[str]] = []

    for field_name, enum_class in STATUS_GROUPS:
        for status in enum_class:
            severity = getattr(
                getattr(
                    status,
                    "severity",
                    status,
                ),
                "value",
                "",
            )
            rows.append(
                [
                    "Status",
                    field_name,
                    status.value,
                    severity,
                    status.description,
                ]
            )

    return rows
