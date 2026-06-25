# Reports

## Effort Summary Report

`Effort_Summary_Report.csv` contains two row types:

- `Effort Summary`: one row per effort with selected counts, severity counts,
  workload category counts, and estimated time.
- `Inventory Detail`: one row per visible inventory item with every status
  column and the full reason text.

This makes the CSV useful both as a summary and as an auditable effort-level
inventory list.

## Issues Report

`Issues_Report.csv` lists rows with validation reasons. It includes one status
column per validation area:

- `Inventory Status`
- `Schedule Status`
- `Location Status`
- `Archive Status`
- `Fix Status`
- `Movement Status`

`Issues_Report_Status_Glossary.csv` is generated with the Issues Report. It
explains each report column and each known status value.

## Updating Report Status Meanings

When adding a new status:

1. Add the enum value in `app/core/models.py`.
2. Add the user-facing reason in `app/core/status_messages.py`.
3. Add the glossary row in `app/reports/status_glossary.py`.
4. Add or update tests that generate the report.

## Release Estimate Report

`Release_Estimate_Report.csv` includes `Thread Count` because estimated time is
calculated from selected inventory volume and the active thread count.

Forecast generation uses `settings.json`:

`reports.forecast_thread_count`

The default is `5` when the setting is not present.

## Release Inventory Report

`Release_Inventory_Report.csv` does not include thread count because it reports
inventory schedule issues, not workload estimates.
