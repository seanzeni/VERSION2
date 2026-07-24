from __future__ import annotations

# Purpose:
#     Central report column schemas.
#
# Used By:
#     Report generators
#     ReportRegistry XLSX conversion
#
# Responsibilities:
#     - Keep CSV/XLSX column names in one place.
#     - Reduce column drift between report formats.
#     - Provide a single update point when report columns change.

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
    ReportColumn("Awareness Status", "HIPPA/ODS informational awareness status."),
    ReportColumn("Packaging Status", "NDVR return-code packaging status."),
    ReportColumn("Reasons", "Detailed validation messages."),
]

ISSUES_GLOSSARY_COLUMNS = [
    ReportColumn("Section"),
    ReportColumn("Field"),
    ReportColumn("Value"),
    ReportColumn("Severity"),
    ReportColumn("Meaning"),
]

EFFORT_SUMMARY_SUMMARY_COLUMNS = [
    ReportColumn("Project"),
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

EFFORT_SUMMARY_INVENTORY_COLUMNS = [
    ReportColumn("Project", "Inventory project or effort ID."),
    ReportColumn("Element", "Mainframe element/program name from inventory."),
    ReportColumn("Type", "Element type."),
    ReportColumn("Selected", "Whether the row is selected for the current run."),
    ReportColumn("Selectable", "Whether the UI allows the row to be selected."),
    ReportColumn("Visible", "Whether the row is visible in the element table."),
    ReportColumn("Severity", "Highest severity across validation statuses."),
    ReportColumn("Inventory Status", "Duplicate/overlap inventory status."),
    ReportColumn("Schedule Status", "SQL schedule comparison status."),
    ReportColumn("Location Status", "NDVR location validation status."),
    ReportColumn("Archive Status", "Archive/program counterpart status."),
    ReportColumn("Fix Status", "FIXP1 warning status."),
    ReportColumn("Movement Status", "Movement marker status."),
    ReportColumn("Resync Status", "Resync/version warning status."),
    ReportColumn("Awareness Status", "HIPPA/ODS informational awareness status."),
    ReportColumn("Packaging Status", "NDVR return-code packaging status."),
    ReportColumn("Reasons", "Detailed validation messages."),
]

EFFORT_SUMMARY_COLUMNS = EFFORT_SUMMARY_INVENTORY_COLUMNS

RELEASE_ESTIMATE_COLUMNS = [
    ReportColumn("Effort"),
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
    ReportColumn("Movement Note"),
]

MOVEMENT_MATCH_COLUMNS = [
    ReportColumn("Release"),
    ReportColumn("Project"),
    ReportColumn("Element"),
    ReportColumn("Type"),
    ReportColumn("Submitter"),
]

HIPPA_LISTENER_COLUMNS = [
    ReportColumn("Release"),
    ReportColumn("Project"),
    ReportColumn("Element"),
    ReportColumn("Type"),
    ReportColumn("Submitter"),
    ReportColumn("Listener"),
    ReportColumn("Listener Transactions"),
]

ODS_ELEMENTS_COLUMNS = MOVEMENT_MATCH_COLUMNS

AFTER_ACTION_COLUMNS = [
    ReportColumn("Release"),
    ReportColumn("Mode"),
    ReportColumn("Move Date"),
    ReportColumn("Project"),
    ReportColumn("Element"),
    ReportColumn("Type"),
    ReportColumn("Expected Env"),
    ReportColumn("Expected System"),
    ReportColumn("Expected Subsystem"),
    ReportColumn("Moved On Date"),
    ReportColumn("NDVR Package"),
    ReportColumn("NDVR RC"),
    ReportColumn("NDVR Date"),
    ReportColumn("NDVR Time"),
    ReportColumn("Reason"),
]

INVENTORY_FORECAST_COLUMNS = [
    ReportColumn("Generated At"),
    ReportColumn("Release"),
    ReportColumn("Next Move"),
    ReportColumn("Move Date"),
    ReportColumn("Project"),
    ReportColumn("Inventory Status"),
    ReportColumn("Element Count"),
    ReportColumn("Reason"),
    ReportColumn("Expected Release"),
    ReportColumn("Inventory Release"),
]

RESYNC_COLUMNS = [
    ReportColumn("Release"),
    ReportColumn("Project"),
    ReportColumn("Element"),
    ReportColumn("Type"),
    ReportColumn("Application"),
    ReportColumn("Element Owner"),
    ReportColumn("Qual Move Date"),
    ReportColumn("Lower Env"),
    ReportColumn("Lower Testing Region"),
    ReportColumn("Lower System"),
    ReportColumn("Lower Subsystem"),
    ReportColumn("Lower Version"),
    ReportColumn("Lower CCID"),
    ReportColumn("Remarks"),
    ReportColumn("Reason"),
]
