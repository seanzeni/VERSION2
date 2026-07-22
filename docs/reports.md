# Reports

## Standalone Runner

`scripts/run_all_reports.py` runs the standalone operational scripts together:
after action, FIXP daily compare, NDVR daily move audit, region inventory audit,
and TO QUAL/TO PROD movement reports.

Use `--date YYYY-MM-DD` for date-driven reports. If omitted, date-driven
reports use the previous calendar day, while FIXP daily compare uses the latest
two available FIXP file dates.

Use `--output <folder>` to create a flat XLSX-only output drop. Existing `.xlsx`
files in that folder are moved to `History` before the new files are published.
Without `--output`, each script uses the normal default output settings and
formats.

## Region Inventory Audit

`scripts/region_inventory_audit.py` reviews upcoming non-Special bundles with
test regions. Before the 15th of the month, the bundle month window starts with
the previous month. On and after the 15th, the previous bundle month is dropped
to match inventory cleanup. Bundles whose production implementation date has
already passed are excluded.

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
- `Awareness Status`
- `Packaging Status`

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
months. Release names containing `Special` are excluded. SQL-linked rows are
included only when their next QUAL or PROD move is today or later. Untracked
inventory remains visible with an unknown move date because SQL does not provide
a schedule for it.

Output is written under:

`<default output folder>/Inventory Issues Forecast/<yyyy-mm-dd>/`

## Resync Report

`Resync_Report.csv`, `.xlsx`, and `.pdf` identify possible resync candidates
from NDVR data using the selected move mode.

Lifecycle ordering is `UNIT1`/`UTDV1` < `SYST1`/`STDV1` < `QUAL1` < `PROD1`.
Older `MAIN1` and `DEVL1` values are still treated as unit-level compatibility
aliases when they appear in historical files.

For QUAL moves, `QUAL1` is the newer source. The report compares that version
against unit and system lifecycle records, skipping the inventory row's current
moving location so the row being promoted does not report itself.

For PROD moves, `PROD1` is the newer source. The report compares that version
against `QUAL1`, unit, and system lifecycle records, again skipping the
inventory row's current moving location. `FIXP1` is always ignored for resync.

## OSG/COPS Report

The OSG/COPS report supports XLSX and PDF only and is generated only for PROD
moves. It includes selected, visible O/X elements with release, project,
element, type, submitter, and movement note. A package archive is suppressed
when its configured APS/COB counterpart is also moving; an unpaired archive
remains in the report with `Package archive` in `Movement Note`.

## HIPPA Listeners And ODS Elements

The HIPPA Listeners and ODS Elements reports match selected, visible movement
rows against their configured CSV reference files. Matching is case-insensitive
on the required `Element` and `Type` columns. The files are loaded once at
startup and are also used during forecast report generation.

Configure `files.hippa_listener_file` and `files.ods_file` with absolute paths
or paths relative to the application folder. HIPPA Listeners also reads
`Listener` and `Listener Transactions` from the CSV and includes those values in
the report and informational Effort Summary reason.

ODS Elements is informational and appears in the ODS Elements report when a
selected movement row matches the configured `Element` + `Type`.

## After Action Report

The `After Action` button in Report Center uses the entered `YYYY-MM-DD` date
independently from the currently selected release. It finds SQL bundles whose
QUAL or PROD date equals that already-passed date, loads the connected inventory
for each matching effort, and compares those elements to the loaded NDVR file.

QUAL after-action checks for matching element/type records in `QUAL1` on the
selected date. PROD after-action checks `PROD1` and also requires the expected
system and subsystem. The report includes the NDVR package, return code, and
time when a matching record is found.

The report supports CSV, XLSX, and PDF using the Report Center format
checkboxes.

## Standalone NDVR Daily Move Audit

`scripts/ndvr_daily_move_audit.py` is intentionally separate from the desktop
program. It scans all `.txt`, `.dat`, and `.csv` files in the configured NDVR
source directory, filters movement records for the requested date, and keeps
only `QUAL1` or `PROD1` records in `PRIVATE1` or `SHARED01`.

By default it audits the previous calendar day:

```powershell
py -3.14 scripts/ndvr_daily_move_audit.py
```

To audit a specific date:

```powershell
py -3.14 scripts/ndvr_daily_move_audit.py --date 2026-07-14
```

The script uses `settings.json` by default and writes XLSX and PDF only under:

`<default output folder>/NDVR Daily Move Audit/<yyyy-mm-dd>/`

Statuses:

- `APPROVED_MOVE`: inventory and SQL show the project was authorized for that
  QUAL/PROD move date.
- `APPROVED_MOVE_AFTER_QUAL_DATE`: QUAL move happened after its QUAL date, but
  before the PROD date passed.
- `TRACKED_NOT_AUTHORIZED_FOR_DATE`: the element/type is in inventory, but no
  matching project had that move date. Expected SQL dates are listed.
- `NOT_TRACKED_IN_INVENTORY`: the element/type moved in NDVR but was not found
  in the inventory file.

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
    "HIPPA Listeners": true,
    "Issues Report": true,
    "ODS Elements": true,
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

## SharePoint Output

Report Center offers `Local` and `SharePoint` destinations. When SharePoint is
selected, the app converts `reports.sharepoint_url` to a Windows WebDAV path and
uses the logged-on user's Microsoft 365 session. It creates a release folder,
moves existing top-level report files into that folder's `History` directory,
and names new files:

`RELEASE_REPORT_NAME_YYYYMMDD_HHMMSS.ext`

Use a direct HTTPS URL to the target document-library folder. The workstation
must have the Windows WebClient service available and the user must already
have access to the SharePoint location.
