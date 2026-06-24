from __future__ import annotations

"""
Purpose:
    Build and hold application-wide services and settings.

Annotations:
    Uses postponed annotations for service and path type hints.

Used By:
    main.py
    MainWindow

Responsibilities:
    - Load settings and resolve configured file paths.
    - Prompt for missing required or optional startup files.
    - Construct shared services used by the UI and reports.
    - Persist remembered file selections back to settings.json.

Notes:
    MainWindow should create UI widgets only.
    AppContext owns service creation.
"""

from pathlib import Path

from app.config.settings_loader import SettingsLoader
from app.core.app_state import AppState
from app.reports.report_registry import ReportRegistry
from app.services.data_loader import DataLoader
from app.services.db_service import DBService
from app.services.element_service import ElementService
from app.services.exporter import Exporter
from app.services.mainframe_location_service import MainframeLocationService
from app.services.stats_service import StatsService
from app.services.status_marker_service import StatusMarkerService
from app.services.validation_service import ValidationService
from app.ui.theme_manager import ThemeManager


class AppContext:
    def __init__(self, base_dir: str | Path, settings_path: str | Path) -> None:
        self.base_dir = Path(base_dir)
        self.settings_path = Path(settings_path)

        self.settings = SettingsLoader(
            self.settings_path,
        ).load()

        input_path = self.resolve_startup_file(
            key="default_input_file",
            title="Select Inventory Spreadsheet",
            filetypes=[
                ("Excel Files", "*.xlsx *.xls"),
                ("All Files", "*.*"),
            ],
            required=True,
            missing_message="No inventory spreadsheet was selected.",
        )
        ndvr_path = self.resolve_startup_file(
            key="default_ndvr_file",
            title="Select NDVR/Mainframe Location File",
            filetypes=[
                ("Text Files", "*.txt *.dat *.csv"),
                ("All Files", "*.*"),
            ],
            required=False,
        )
        output_path = self.resolve_path(
            self.settings["files"].get(
                "default_output_folder",
                "Output",
            )
        )

        if input_path is None:
            raise FileNotFoundError("No inventory spreadsheet was selected.")

        self.input_file = Path(input_path)
        self.output_folder = Path(output_path)

        self.state = AppState(
            current_xls_path=input_path,
            current_ndvr_path=ndvr_path
        )

        self.location_service: MainframeLocationService | None = None
        
        if self.state.current_ndvr_path is not None:
            self.load_location_file(self.state.current_ndvr_path)

        self.ui_settings = self.settings["ui"]
        self.workload_settings = self.settings["workload"]
        self.selection_rules = self.settings["selection_rules"]
        self.archive_pairs = self.settings["type_archive_pairs"]
        self.status_markers = self.settings["status_markers"]
        self.db_settings = self.settings["database"]
        self.required_columns = self.settings["required_columns"]

        self.theme_manager = ThemeManager(
            ui_settings=self.ui_settings,
        )

        self.data_loader = DataLoader(
            file_path=self.input_file,
            required_columns=self.required_columns,
        )
        self.data_loader.load()

        self.db_service = DBService(
            db_settings=self.db_settings,
        )

        self.element_service = ElementService()

        self.status_marker_service = StatusMarkerService(
            status_markers=self.status_markers,
        )

        self.validation_service = ValidationService(
            selection_rules=self.selection_rules,
            archive_pairs=self.archive_pairs,
            status_marker_service=self.status_marker_service,
        )

        self.stats_service = StatsService(
            workload_settings=self.workload_settings,
        )

        self.exporter = Exporter(
            settings=self.settings,
            base_dir=self.base_dir,
        )

        self.report_registry = ReportRegistry(
            stats_service=self.stats_service,
        )

    def load_location_file(
        self,
        file_path: str | Path,
    ) -> MainframeLocationService:
        path = self.resolve_path(file_path)

        service = MainframeLocationService()
        service.load_file(path)

        self.location_service = service
        self.state.current_ndvr_path = path

        self.save_file_setting_if_needed(
            key="default_ndvr_file",
            value=path,
        )

        return service

    def resolve_startup_file(
        self,
        key: str,
        title: str,
        filetypes: list[tuple[str, str]],
        required: bool,
        missing_message: str = "",
    ) -> Path | None:
        configured_value = str(
            self.settings["files"].get(
                key,
                "",
            )
        ).strip()

        configured_path = (
            self.resolve_path(configured_value)
            if configured_value
            else None
        )

        if configured_path is not None and configured_path.exists():
            return configured_path

        selected_file = self.prompt_for_file(
            title=title,
            filetypes=filetypes,
        )

        if selected_file is None:
            if required:
                raise FileNotFoundError(missing_message)

            return None

        self.save_file_setting_if_needed(
            key=key,
            value=selected_file,
        )

        return selected_file

    def resolve_path(
        self,
        file_path: str | Path,
    ) -> Path:
        path = Path(file_path)

        if path.is_absolute():
            return path

        return self.base_dir / path

    def prompt_for_file(
        self,
        title: str,
        filetypes: list[tuple[str, str]],
    ) -> Path | None:
        from tkinter import filedialog

        selected = filedialog.askopenfilename(
            title=title,
            filetypes=filetypes,
        )

        if not selected:
            return None

        return Path(selected)

    def save_file_setting_if_needed(
        self,
        key: str,
        value: Path,
    ) -> None:
        if not self.settings.get("files", {}).get("remember_last_used_files", True):
            return

        current_value = str(
            self.settings["files"].get(
                key,
                "",
            )
        )

        new_value = str(value)

        if current_value == new_value:
            return

        self.settings["files"][key] = new_value

        SettingsLoader.save(
            settings_path=self.settings_path,
            settings=self.settings,
        )
