# Settings And Deployment

## Files

`settings.json` is expected to live next to the application when running from
source or from a packaged executable.

Important file settings:

- `directory.person_lookup_url`: optional HTTP endpoint used by standalone FIXP
  daily stats to translate mainframe IDs before resolving names through AD. The
  configured URL can end before or after `/search`; the script adds
  `?criteria=<id>`.
- `files.default_fixp_db`: optional Access database containing `tblFIXP1` rows
  used to enrich the standalone FIXP daily stats report.
- `files.default_fixp_folder`: folder containing rotating
  `FIXP-YYYYMMDD_HHMMSS.txt` snapshots for the standalone FIXP daily stats
  report.
- `files.default_input_file`: inventory spreadsheet path.
- `files.default_input_folder`: folder used when prompting for inventory files.
- `files.default_ndvr_file`: NDVR/mainframe location file path or directory. If
  this points to a directory, the app loads the newest `.txt`, `.dat`, or `.csv`
  file in that directory so timestamped NDVR drops can rotate without changing
  settings.
- `files.default_output_folder`: base folder for exports, reports, history, and
  forecast output.
- `files.fixp_32bit_python`: command used by 64-bit Python to run the 32-bit
  Access helper when all Access drivers are 32-bit.
- `files.hippa_listener_file`: CSV containing HIPPA Listeners `Element`, `Type`,
  `Listener`, and `Listener Transactions` columns.
- `files.ods_file`: CSV containing ODS Elements `Element` and `Type` reference
  columns.
- `files.remember_last_used_files`: when `true`, selected Excel and NDVR paths
  are written back to `settings.json`.

The older `ui.remember` and `ui.remember_window_size` settings were removed
because they were not wired to application behavior.

## Input File Notes

NDVR/mainframe location files are parsed as fixed-width fields separated by one
space. The current order is:

`Element`, `Type`, `System`, `Subsystem`, `Env`, `DateGenerated`,
`TimeGenerated`, `Version`, `User`, `CCID`, `Comments`, `NDVR RC`,
`NDVR Package`, `SourceDate`, `SourceTime`.

`System` is 8 characters and `Subsystem` is 4 characters. `NDVR RC` is optional
but, when present, must be numeric. `SourceDate` and `SourceTime` are optional
and are used by the standalone FIXP daily stats report.

HIPPA Listeners CSV files require `Element`, `Type`, `Listener`, and
`Listener Transactions`. ODS Elements CSV files require `Element` and `Type`.
Both are loaded once when the application starts.

FIXP daily stats uses rotating `FIXP-YYYYMMDD_HHMMSS.txt` files from
`files.default_fixp_folder` and compares the latest two available file dates
when no date is supplied.

## Forecast Settings

Forecast report generation is controlled by `settings.json`, not the visible
Report Center checkboxes.

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
  "forecast_thread_count": 5,
  "sharepoint_url": "https://tenant.sharepoint.com/sites/site/Shared Documents/Reports",
  "use_sharepoint": false
}
```

Set a report or format to `false` to exclude it from forecast generation.
`reports.include_empty_reports_default` controls whether Report Center creates
empty selected reports when no rows match.
Set `use_sharepoint` to choose the initial Report Center destination. Users can
switch between Local and SharePoint with the radio buttons. SharePoint output
uses the logged-on user's Windows WebDAV session; no password is stored.

## Selection Rule Settings

`selection_rules.ndvr_rc_max_allowed` defaults to `8`. Any loaded expected
source NDVR record for the same element/type with a higher return code sets
`Packaging Status` to `NDVR_RC_TOO_HIGH`. Archive rows are excluded from this
return-code blocker.

Common selectable switches:

- `already_in_environment_selectable`: rows marked already in PROD/QUAL.
- `assignment_error_selectable`: inventory assigned to a different release than
  the selected release; default is `true`.
- `archive_in_qual_selectable`: archive rows hidden from normal QUAL moves.
- `do_not_move_selectable`: rows marked DO NOT MOVE.
- `duplicate_selectable`: duplicate element/type rows.
- `effort_release_mismatch_selectable`: SQL effort/release mismatch rows.
- `highly_likely_missing_program_selectable`: archive row where the opposite
  program appears in a lower environment but not in selected inventory.
- `inventory_not_in_release_selectable`: inventory row connected to another
  release.
- `inventory_when_sql_no_inventory_selectable`: inventory exists although SQL
  marks the effort as no-inventory.
- `marked_already_there_missing_selectable`: marker says already in PROD/QUAL
  but NDVR does not confirm that location.
- `missing_ndvr_selectable`: missing from expected source on or after expected
  date; recommended/default is `false`.
- `not_expected_ndvr_yet_selectable`: PROD row missing from `QUAL1` before its
  upstream QUAL move date; recommended/default is `false`.
- `ndvr_rc_too_high_selectable`: expected source NDVR return code exceeds the
  configured threshold; recommended/default is `false`.
- `overlap_selectable`: overlapping inventory rows.
- `potential_missing_archive_selectable`: possible missing archive counterpart.
- `potential_missing_program_move_selectable`: possible missing moving program
  counterpart.
- `sql_expected_inventory_missing_selectable`: SQL expects inventory but none
  was found.

## Standalone Report Output

Standalone operational scripts write directly to the configured output folder or
the folder passed with `--output-folder`. Previous files for the same report/date
stem are moved into `History` after the replacement file has been generated.

`scripts/run_all_reports.py --output <folder>` creates a flat XLSX-only drop in
the selected folder. It stages all new workbooks first, moves existing `.xlsx`
files in the drop folder to `History`, then publishes the new workbooks.

Current standalone file stems:

- `Effort_Move_Status_DD_MMM_YYYY`
- `FIXP_Daily_Stats_DD_MMM_YYYY`
- `Global_Resync_DD_MMM_YYYY`
- `NDVR_Commercial_Audit_DD_MMM_YYYY`
- `Development_Region_Audit_DD_MMM_YYYY`
- `IN_PROD_DD_MMM_YYYY`
- `IN_QUAL_DD_MMM_YYYY`

## PyInstaller

A PyInstaller-built Windows executable does not require Python to be installed
on the target workstation. PyInstaller bundles the Python runtime and imported
Python packages.

External dependencies may still be required on the workstation:

- ODBC Driver 17 for SQL Server.
- Access to configured network paths.
- `settings.json` next to the executable.
- Inventory and NDVR files referenced by settings.

Example build command:

```powershell
pyinstaller --onefile --windowed --name CoordinationModule main.py
```

Keep `settings.json` external if users need to edit paths, report settings, or
forecast options without rebuilding the executable.
