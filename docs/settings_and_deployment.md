# Settings And Deployment

## Files

`settings.json` is expected to live next to the application when running from
source or from a packaged executable.

Important file settings:

- `files.default_input_file`: inventory spreadsheet path.
- `files.default_ndvr_file`: NDVR/mainframe location file path.
- `files.default_output_folder`: base folder for exports, reports, history, and
  forecast output.
- `files.hipaa_listener_file`: workbook containing HIPAA Listener `Element` and
  `Type` reference columns.
- `files.ods_file`: workbook containing ODS `Element` and `Type` reference
  columns.
- `files.remember_last_used_files`: when `true`, selected Excel and NDVR paths
  are written back to `settings.json`.

The older `ui.remember` and `ui.remember_window_size` settings were removed
because they were not wired to application behavior.

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
    "HIPAA Listener Report": true,
    "Issues Report": true,
    "ODS Report": true,
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
Set `use_sharepoint` to choose the initial Report Center destination. Users can
switch between Local and SharePoint with the radio buttons. SharePoint output
uses the logged-on user's Windows WebDAV session; no password is stored.

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
