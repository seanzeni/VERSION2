# Reports

## Effort Summary Report

`Effort_Summary_Report.csv` contains one row per inventory item with every
status column and the full reason text, including hidden rows such as
marker-hidden rows. It does not include separate effort-level summary rows.

`Effort_Summary_Report.xlsx` contains:

- `Summary`: one row per effort with selected counts, severity counts, workload
  category counts, and estimated time.
- `Inventory`: one row per inventory item with every status column and reason.
- `Information`: column and status explanations.

`Effort_Summary_Report.pdf` starts with a summary page and then adds one detail
page per effort. The effort detail pages show counts by warning/error status
type, such as overlaps, duplicates, missing archives, missing programs, not
found, FIXP1, and resync warnings. Individual element issue rows are omitted to
keep the PDF focused on effort-level risk.

## Issues Report

`Issues_Report.csv` and `Issues_Report.xlsx` list rows with validation reasons.
They include one status column per validation area:

- `Inventory Status`
- `Schedule Status`
- `Location Status`
- `Archive Status`
- `Fix Status`
- `Movement Status`

`Issues_Report_Status_Glossary.csv` is generated with the Issues Report. In XLSX
output, the same glossary is included as a second sheet. It explains each report
column and each known status value.

## Updating Report Status Meanings

When adding a new status:

1. Add the enum value in `app/core/models.py`.
2. Add the status `description` in the same enum.
3. Add the user-facing reason in `app/core/status_messages.py`.
4. Add or update tests that generate the report.

When adding a report column, update the matching schema in
`app/reports/report_schemas.py`. CSV and XLSX reports use those schemas, and the
Issues Report glossary uses the schema descriptions.

## Release Estimate Report

`Release_Estimate_Report.csv` and `.xlsx` contain effort-level detail. Each
effort row includes its move date, selected element count, workload category
counts, category minutes, and estimated time. A `TOTAL` row summarizes the whole
release.

`Thread Count` is included in the spreadsheet because estimated time is
calculated from selected inventory volume and the active thread count.

`Release_Estimate_Report.pdf` is a rollup instead of effort-level detail. It
shows global run metadata at the top:

- `Generated`
- `Bundle`
- `Mode`
- `Thread Count`

Then it shows the overall number of efforts, selected elements, estimated time,
and total element counts by workload category. The PDF estimated time is summed
from the same effort-level estimates as the spreadsheet `TOTAL` row so rounding
stays consistent between formats.

Forecast generation uses `settings.json`:

`reports.forecast_thread_count`

The default is `5` when the setting is not present.

For forecast runs only, the Release Estimate Report counts all inventory rows in
the forecasted efforts even when current validation would leave them unselected,
because the forecast is meant to approximate future move volume. Rows marked
`DO_NOT_MOVE`, `MARKED_IN_PROD`, or `MARKED_IN_QUAL` are excluded because they
are not requesting movement.

## Release Inventory Report

`Release_Inventory_Report.csv` does not include thread count because it reports
inventory schedule issues, not workload estimates.

This report is limited to inventory/release schedule issues:

- SQL expected inventory but no inventory rows were found.
- SQL says no inventory or the effort is withdrawn, but inventory rows exist.
- Inventory contains a project that is not connected to the selected SQL release.
- Inventory release and RSET/SQL release disagree.

Element-level validation issues, such as missing NDVR location, duplicate rows,
archive warnings, marker warnings, and FIXP1 warnings, belong in the Issues
Report instead.

For release mismatches, `Expected Release` is the RSET/SQL release and
`Inventory Release` is the release from the inventory file.

## Inventory Issues Forecast

The `Inventory Issues` button in Report Center creates one consolidated report
across upcoming releases. It uses the CSV, XLSX, and PDF format selections shown
in Report Center and reports:

- SQL expects inventory, but no inventory exists.
- Inventory is assigned to a different release than SQL expects.
- Inventory exists for a project that is not connected to SQL.
- SQL marks an upcoming effort as no inventory, but inventory exists.

Regular `YYYY/MM...` releases include the current month plus the following three
months. Release names containing `Special` use the current month plus one month.
SQL-linked rows are included only when their next QUAL or PROD move is today or
later. Untracked inventory remains visible with an unknown move date because SQL
does not provide a schedule for it.

Output is written under:

`<default output folder>/Inventory Issues Forecast/<yyyy-mm-dd>/`

## Resync Report

`Resync_Report.csv`, `.xlsx`, and `.pdf` identify possible resync candidates
from NDVR data. A row appears when a matching element/type has a higher version
or different latest CCID in a higher environment while a lower version exists in
a lower environment.

## Forecast Reports

The Forecast button generates reports from settings, not from the visible report
format checkboxes in Report Center.

Use `settings.json`:

```json
"reports": {
  "forecast_formats": {
    "csv": true,
    "pdf": true,
    "xlsx": true
  },
  "forecast_reports": {
    "Effort Summary Report": true,
    "Issues Report": true,
    "OSG/COPS Report": true,
    "Release Estimate Report": true,
    "Release Inventory Report": true,
    "Resync Report": true
  },
  "forecast_thread_count": 5
}
```

Set any format or report to `false` to exclude it from forecast generation.

Forecast output is written under:

`<default output folder>/3 Month Forecast/<yyyy-mm>/<QUAL or PROD>/<release name>/`

The Report Center progress area is scrollable so long forecast summaries remain
visible without resizing the window.
