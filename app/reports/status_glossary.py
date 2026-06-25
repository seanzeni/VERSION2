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


ISSUES_COLUMN_GLOSSARY: list[dict[str, str]] = [
    {
        "section": "Column",
        "field": "Element",
        "value": "",
        "severity": "",
        "meaning": "Mainframe element/program name from inventory.",
    },
    {
        "section": "Column",
        "field": "Type",
        "value": "",
        "severity": "",
        "meaning": "Element type, such as OCOB, OAPS, JCL, PROC, or related type.",
    },
    {
        "section": "Column",
        "field": "Project",
        "value": "",
        "severity": "",
        "meaning": "Inventory project or effort ID.",
    },
    {
        "section": "Column",
        "field": "Release",
        "value": "",
        "severity": "",
        "meaning": "Release value listed in inventory.",
    },
    {
        "section": "Column",
        "field": "Expected System",
        "value": "",
        "severity": "",
        "meaning": "Expected system parsed from inventory or source data.",
    },
    {
        "section": "Column",
        "field": "Expected Region",
        "value": "",
        "severity": "",
        "meaning": "Expected region parsed from inventory or source data.",
    },
    {
        "section": "Column",
        "field": "Severity",
        "value": "",
        "severity": "",
        "meaning": "Highest severity across all status columns for the row.",
    },
    {
        "section": "Column",
        "field": "Reasons",
        "value": "",
        "severity": "",
        "meaning": "Detailed messages explaining why non-OK statuses were assigned.",
    },
]


STATUS_GLOSSARY: list[dict[str, str]] = [
    {
        "section": "Status",
        "field": "Severity",
        "value": Severity.INFO.value,
        "severity": Severity.INFO.value,
        "meaning": "Informational state. Usually does not block selection by itself.",
    },
    {
        "section": "Status",
        "field": "Severity",
        "value": Severity.WARNING.value,
        "severity": Severity.WARNING.value,
        "meaning": "Review recommended. Selection depends on the specific rule and settings.",
    },
    {
        "section": "Status",
        "field": "Severity",
        "value": Severity.ERROR.value,
        "severity": Severity.ERROR.value,
        "meaning": "Blocking or high-risk condition that normally requires correction.",
    },
    {
        "section": "Status",
        "field": "Inventory Status",
        "value": InventoryStatus.OK.value,
        "severity": InventoryStatus.OK.severity.value,
        "meaning": "No duplicate or overlap issue was detected.",
    },
    {
        "section": "Status",
        "field": "Inventory Status",
        "value": InventoryStatus.OVERLAP.value,
        "severity": InventoryStatus.OVERLAP.severity.value,
        "meaning": "Same element/type appears in more than one selected project.",
    },
    {
        "section": "Status",
        "field": "Inventory Status",
        "value": InventoryStatus.DUPLICATE.value,
        "severity": InventoryStatus.DUPLICATE.severity.value,
        "meaning": "Same element/type appears more than once within the same project.",
    },
    {
        "section": "Status",
        "field": "Schedule Status",
        "value": ScheduleStatus.OK.value,
        "severity": ScheduleStatus.OK.severity.value,
        "meaning": "Inventory project matches the SQL release schedule.",
    },
    {
        "section": "Status",
        "field": "Schedule Status",
        "value": ScheduleStatus.INVENTORY_NOT_IN_RELEASE.value,
        "severity": ScheduleStatus.INVENTORY_NOT_IN_RELEASE.severity.value,
        "meaning": "Inventory project is not connected to the selected SQL release.",
    },
    {
        "section": "Status",
        "field": "Schedule Status",
        "value": ScheduleStatus.INVENTORY_WHEN_SQL_NO_INVENTORY.value,
        "severity": ScheduleStatus.INVENTORY_WHEN_SQL_NO_INVENTORY.severity.value,
        "meaning": "Inventory exists for an effort SQL marks as no-inventory or withdrawn.",
    },
    {
        "section": "Status",
        "field": "Schedule Status",
        "value": ScheduleStatus.SQL_EXPECTED_INVENTORY_MISSING.value,
        "severity": ScheduleStatus.SQL_EXPECTED_INVENTORY_MISSING.severity.value,
        "meaning": "SQL expected inventory, but no inventory rows were found.",
    },
    {
        "section": "Status",
        "field": "Schedule Status",
        "value": ScheduleStatus.EFFORT_RELEASE_MISMATCH.value,
        "severity": ScheduleStatus.EFFORT_RELEASE_MISMATCH.severity.value,
        "meaning": "Inventory release does not match the release SQL associates with the effort.",
    },
    {
        "section": "Status",
        "field": "Location Status",
        "value": LocationStatus.OK.value,
        "severity": LocationStatus.OK.severity.value,
        "meaning": "Location validation did not find a problem or was not required.",
    },
    {
        "section": "Status",
        "field": "Location Status",
        "value": LocationStatus.FOUND.value,
        "severity": LocationStatus.FOUND.severity.value,
        "meaning": "Element/type was found in the expected NDVR location.",
    },
    {
        "section": "Status",
        "field": "Location Status",
        "value": LocationStatus.NOT_FOUND.value,
        "severity": LocationStatus.NOT_FOUND.severity.value,
        "meaning": "Element/type was not found in the expected NDVR location.",
    },
    {
        "section": "Status",
        "field": "Archive Status",
        "value": ArchiveStatus.OK.value,
        "severity": ArchiveStatus.OK.severity.value,
        "meaning": "No archive counterpart issue was detected.",
    },
    {
        "section": "Status",
        "field": "Archive Status",
        "value": ArchiveStatus.ARCHIVE_IN_QUAL.value,
        "severity": ArchiveStatus.ARCHIVE_IN_QUAL.severity.value,
        "meaning": "Archive row is intentionally hidden for normal QUAL movement.",
    },
    {
        "section": "Status",
        "field": "Archive Status",
        "value": ArchiveStatus.POTENTIAL_MISSING_ARCHIVE.value,
        "severity": ArchiveStatus.POTENTIAL_MISSING_ARCHIVE.severity.value,
        "meaning": "Program/archive counterpart appears to be missing from selected inventory.",
    },
    {
        "section": "Status",
        "field": "Archive Status",
        "value": ArchiveStatus.POTENTIAL_MISSING_PROGRAM_MOVE.value,
        "severity": ArchiveStatus.POTENTIAL_MISSING_PROGRAM_MOVE.severity.value,
        "meaning": "Archive move may be missing its corresponding program move.",
    },
    {
        "section": "Status",
        "field": "Fix Status",
        "value": FixStatus.OK.value,
        "severity": FixStatus.OK.severity.value,
        "meaning": "Element/type was not found in FIXP1.",
    },
    {
        "section": "Status",
        "field": "Fix Status",
        "value": FixStatus.EXISTS_IN_FIXP1.value,
        "severity": FixStatus.EXISTS_IN_FIXP1.severity.value,
        "meaning": "Element/type also exists in FIXP1 and should be reviewed.",
    },
    {
        "section": "Status",
        "field": "Movement Status",
        "value": MovementStatus.OK.value,
        "severity": MovementStatus.OK.severity.value,
        "meaning": "No movement marker issue was detected.",
    },
    {
        "section": "Status",
        "field": "Movement Status",
        "value": MovementStatus.DO_NOT_MOVE.value,
        "severity": MovementStatus.DO_NOT_MOVE.severity.value,
        "meaning": "Inventory row is marked do not move and is hidden/unselectable.",
    },
    {
        "section": "Status",
        "field": "Movement Status",
        "value": MovementStatus.MARKED_ALREADY_THERE_BUT_MISSING.value,
        "severity": MovementStatus.MARKED_ALREADY_THERE_BUT_MISSING.severity.value,
        "meaning": "Row says it is already in target, but NDVR did not confirm it.",
    },
    {
        "section": "Status",
        "field": "Resync Status",
        "value": ResyncStatus.OK.value,
        "severity": ResyncStatus.OK.severity.value,
        "meaning": "No resync/version warning was detected.",
    },
    {
        "section": "Status",
        "field": "Resync Status",
        "value": ResyncStatus.HIGHER_VERSION_EXISTS.value,
        "severity": ResyncStatus.HIGHER_VERSION_EXISTS.severity.value,
        "meaning": "A higher version exists in a higher environment.",
    },
]


def get_issues_glossary_rows() -> list[list[str]]:
    return [
        [
            item["section"],
            item["field"],
            item["value"],
            item["severity"],
            item["meaning"],
        ]
        for item in ISSUES_COLUMN_GLOSSARY + STATUS_GLOSSARY
    ]
