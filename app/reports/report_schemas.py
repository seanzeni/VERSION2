from __future__ import annotations

"""
Purpose:
    Central report column schemas.

Used By:
    Report generators
    ReportRegistry XLSX conversion

Responsibilities:
    - Keep CSV/XLSX column names in one place.
    - Reduce column drift between report formats.
    - Provide a single update point when report columns change.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReportColumn:
    name: str
    description: str = ""


def names(columns: list[ReportColumn]) -> list[str]:
    return [column.name for column in columns]


ISSUES_COLUMNS = [
    ReportColumn("Element", "Mainframe element/program name from inventory."),
    ReportColumn("Type", "Element type."),
    ReportColumn("Project", "Inventory project or effort ID."),
    ReportColumn("Release", "Inventory release value."),
    ReportColumn("Expected System", "Expected system parsed from inventory."),
    ReportColumn("Expected Region", "Expected region parsed from inventory."),
    ReportColumn("Severity", "Highest severity across validation statuses."),
    ReportColumn("Inventory Status", "Duplicate/overlap inventory status."),
    ReportColumn("Schedule Status", "SQL schedule comparison status."),
    ReportColumn("Location Status", "NDVR location validation status."),
    ReportColumn("Archive Status", "Archive/program counterpart status."),
    ReportColumn("Fix Status", "FIXP1 warning status."),
    ReportColumn("Movement Status", "Movement marker status."),
    ReportColumn("Reasons", "Detailed validation messages."),
]

ISSUES_GLOSSARY_COLUMNS = [
    ReportColumn("Section"),
    ReportColumn("Field"),
    ReportColumn("Value"),
    ReportColumn("Severity"),
    ReportColumn("Meaning"),
]

EFFORT_SUMMARY_COLUMNS = [
    ReportColumn("Row Type"),
    ReportColumn("Project"),
    ReportColumn("Element"),
    ReportColumn("Type"),
    ReportColumn("Selected"),
    ReportColumn("Selectable"),
    ReportColumn("Visible"),
    ReportColumn("Severity"),
    ReportColumn("Inventory Status"),
    ReportColumn("Schedule Status"),
    ReportColumn("Location Status"),
    ReportColumn("Archive Status"),
    ReportColumn("Fix Status"),
    ReportColumn("Movement Status"),
    ReportColumn("Resync Status"),
    ReportColumn("Reasons"),
    ReportColumn("Selected Elements"),
    ReportColumn("Errors"),
    ReportColumn("Warnings"),
    ReportColumn("Info"),
    ReportColumn("JCL Count"),
    ReportColumn("Non Compile Count"),
    ReportColumn("COBOL Count"),
    ReportColumn("APS Count"),
    ReportColumn("X Elements Count"),
    ReportColumn("Linkdeck Count"),
    ReportColumn("Estimated Time"),
]

RELEASE_ESTIMATE_COLUMNS = [
    ReportColumn("Move Date"),
    ReportColumn("Thread Count"),
    ReportColumn("Selected Elements"),
    ReportColumn("JCL Count"),
    ReportColumn("Non Compile Count"),
    ReportColumn("COBOL Count"),
    ReportColumn("APS Count"),
    ReportColumn("X Elements Count"),
    ReportColumn("Linkdeck Count"),
    ReportColumn("JCL Minutes"),
    ReportColumn("Non Compile Minutes"),
    ReportColumn("COBOL Minutes"),
    ReportColumn("APS Minutes"),
    ReportColumn("X Elements Minutes"),
    ReportColumn("Linkdeck Minutes"),
    ReportColumn("Estimated Time"),
]

RELEASE_INVENTORY_COLUMNS = [
    ReportColumn("Generated At"),
    ReportColumn("Release"),
    ReportColumn("Mode"),
    ReportColumn("Project"),
    ReportColumn("Inventory Status"),
    ReportColumn("Element Count"),
    ReportColumn("Reason"),
    ReportColumn("Expected Release"),
    ReportColumn("Inventory Release"),
]

OSG_COPS_COLUMNS = [
    ReportColumn("Release"),
    ReportColumn("Project"),
    ReportColumn("Element"),
    ReportColumn("Type"),
    ReportColumn("Submitter"),
    ReportColumn("Application"),
    ReportColumn("Package"),
    ReportColumn("Area"),
    ReportColumn("Service"),
]
