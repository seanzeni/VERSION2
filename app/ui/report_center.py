from __future__ import annotations

# Purpose:
#     Non-modal report generation center.
#
# Used By:
#     MainWindow
#
# Responsibilities:
#     - Display available reports.
#     - Let the user choose one or more reports.
#     - Let the user choose CSV/XLSX/PDF output.
#     - Let the user include/exclude empty reports.
#     - Let the user override the output folder.
#     - Generate selected reports.
#     - Show generation progress and results.
#
# Notes:
#     This window should not build report content directly.
#     Report content belongs inside report classes.

from datetime import date
from datetime import datetime
from pathlib import Path
from tkinter import filedialog
from tkinter import messagebox

import customtkinter as ctk

from app.reports.report_utils import archive_existing_reports
from app.reports.report_utils import archive_matching_reports
from app.reports.report_utils import build_report_file_prefix
from app.reports.report_utils import get_date_folder_path
from app.reports.report_utils import prefix_report_files
from app.reports.report_utils import safe_release_name
from app.services.after_action_service import AfterActionService
from app.services.forecast_service import ForecastService
from app.services.inventory_forecast_service import InventoryForecastService
from app.services.sharepoint_report_service import SharePointReportService


class ReportCenter(ctk.CTkToplevel):
    def __init__(
        self,
        parent,
        report_registry,
        app_state,
        base_output_folder: Path,
        context=None,
    ) -> None:
        super().__init__(parent)

        self.report_registry = report_registry
        self.app_state = app_state
        self.base_output_folder = Path(base_output_folder)
        self.context = context

        self.title("Report Center")
        self.geometry("720x620")
        self.minsize(680, 560)
        self.transient(parent)

        self.report_vars: dict[str, ctk.BooleanVar] = {}
        self.csv_var = ctk.BooleanVar(value=True)
        self.xlsx_var = ctk.BooleanVar(value=True)
        self.pdf_var = ctk.BooleanVar(value=True)
        self.include_empty_var = ctk.BooleanVar(value=False)
        reports_settings = (
            self.context.settings.get("reports", {}) if self.context is not None else {}
        )
        self.destination_var = ctk.StringVar(
            value=(
                "sharepoint"
                if reports_settings.get("use_sharepoint", False)
                else "local"
            )
        )

        self.output_folder_var = ctk.StringVar(
            value=str(
                get_date_folder_path(
                    release=self.app_state.release,
                    base_path=self.base_output_folder,
                )
            )
        )

        self.progress_var = ctk.DoubleVar(value=0)
        self.current_report_var = ctk.StringVar(value="Ready")
        self.after_action_date_var = ctk.StringVar(value=date.today().isoformat())

        self._build_ui()
        self.after(
            100,
            self._bring_to_front,
        )

    def _bring_to_front(
        self,
    ) -> None:
        self.lift()
        self.focus_force()

    def _build_ui(
        self,
    ) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkLabel(
            self,
            text="Report Center",
            font=ctk.CTkFont(size=22, weight="bold"),
        )
        header.grid(row=0, column=0, sticky="w", padx=18, pady=(18, 8))

        body = ctk.CTkScrollableFrame(self, corner_radius=10)
        body.grid(row=1, column=0, sticky="nsew", padx=18, pady=8)
        body.grid_columnconfigure(0, weight=1)

        self._build_report_selection(body)
        self._build_output_options(body)
        self._build_progress_area(body)

        button_bar = ctk.CTkFrame(self, fg_color="transparent")
        button_bar.grid(row=2, column=0, sticky="ew", padx=18, pady=(8, 18))

        ctk.CTkButton(
            button_bar,
            text="Generate Selected",
            command=self.generate_selected,
            width=160,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            button_bar,
            text="Generate Forecast",
            command=self.generate_forecast,
            width=160,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            button_bar,
            text="Inventory Issues",
            command=self.generate_inventory_forecast,
            width=150,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            button_bar,
            text="After Action",
            command=self.generate_after_action,
            width=135,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            button_bar,
            text="Close",
            command=self.destroy,
            width=120,
        ).pack(side="right")

    def _build_report_selection(
        self,
        parent,
    ) -> None:
        frame = ctk.CTkFrame(parent, corner_radius=8)
        frame.grid(row=0, column=0, sticky="ew", padx=12, pady=12)
        frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            frame,
            text="Available Reports",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 4))

        ctk.CTkButton(
            frame,
            text="Select All Reports",
            command=self.select_all_reports,
            width=160,
        ).grid(row=0, column=1, sticky="e", padx=12, pady=(10, 4))

        ctk.CTkButton(
            frame,
            text="Clear All Reports",
            command=self.clear_all_reports,
            width=160,
        ).grid(row=0, column=2, sticky="e", padx=(0, 12), pady=(10, 4))

        for row_index, report_name in enumerate(
            self.report_registry.get_names(), start=1
        ):
            var = ctk.BooleanVar(value=True)
            self.report_vars[report_name] = var

            ctk.CTkCheckBox(
                frame,
                text=report_name,
                variable=var,
            ).grid(row=row_index, column=0, columnspan=2, sticky="w", padx=18, pady=3)

    def _build_output_options(
        self,
        parent,
    ) -> None:
        frame = ctk.CTkFrame(parent, corner_radius=8)
        frame.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))
        frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            frame,
            text="Output",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 4))

        format_frame = ctk.CTkFrame(
            frame,
            fg_color="transparent",
        )
        format_frame.grid(row=1, column=0, columnspan=3, sticky="w", padx=18, pady=4)

        ctk.CTkCheckBox(
            format_frame,
            text="CSV",
            variable=self.csv_var,
        ).pack(side="left", padx=(0, 14))

        ctk.CTkCheckBox(
            format_frame,
            text="XLSX",
            variable=self.xlsx_var,
        ).pack(side="left", padx=(0, 14))

        ctk.CTkCheckBox(
            format_frame,
            text="PDF where supported",
            variable=self.pdf_var,
        ).pack(side="left")

        ctk.CTkCheckBox(
            frame,
            text="Include Empty Reports",
            variable=self.include_empty_var,
        ).grid(row=2, column=0, columnspan=2, sticky="w", padx=18, pady=4)

        destination_frame = ctk.CTkFrame(frame, fg_color="transparent")
        destination_frame.grid(
            row=3, column=0, columnspan=3, sticky="w", padx=18, pady=4
        )
        ctk.CTkRadioButton(
            destination_frame,
            text="Local",
            variable=self.destination_var,
            value="local",
        ).pack(side="left", padx=(0, 18))
        ctk.CTkRadioButton(
            destination_frame,
            text="SharePoint",
            variable=self.destination_var,
            value="sharepoint",
        ).pack(side="left")

        ctk.CTkLabel(
            frame,
            text="Folder",
        ).grid(row=4, column=0, sticky="w", padx=18, pady=(10, 4))

        ctk.CTkEntry(
            frame,
            textvariable=self.output_folder_var,
        ).grid(row=5, column=0, columnspan=2, sticky="ew", padx=(18, 8), pady=(0, 12))

        ctk.CTkButton(
            frame,
            text="Browse...",
            command=self.browse_folder,
            width=100,
        ).grid(row=5, column=2, sticky="e", padx=(0, 18), pady=(0, 12))

        ctk.CTkLabel(
            frame,
            text="After Action Date",
        ).grid(row=6, column=0, sticky="w", padx=18, pady=(0, 4))

        ctk.CTkEntry(
            frame,
            textvariable=self.after_action_date_var,
            width=160,
        ).grid(row=7, column=0, sticky="w", padx=18, pady=(0, 12))

    def _build_progress_area(
        self,
        parent,
    ) -> None:
        frame = ctk.CTkFrame(parent, corner_radius=8)
        frame.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 12))
        frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            frame,
            text="Progress",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 4))

        self.progress_bar = ctk.CTkProgressBar(
            frame,
            variable=self.progress_var,
        )
        self.progress_bar.grid(row=1, column=0, sticky="ew", padx=18, pady=(4, 8))
        self.progress_bar.set(0)

        ctk.CTkLabel(
            frame,
            textvariable=self.current_report_var,
        ).grid(row=2, column=0, sticky="w", padx=18, pady=(0, 6))

        self.results_textbox = ctk.CTkTextbox(
            frame,
            height=120,
            wrap="word",
        )
        self.results_textbox.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 12))
        self.results_textbox.configure(state="disabled")

    def select_all_reports(
        self,
    ) -> None:
        for var in self.report_vars.values():
            var.set(True)

    def clear_all_reports(
        self,
    ) -> None:
        for var in self.report_vars.values():
            var.set(False)

    def browse_folder(
        self,
    ) -> None:
        selected = filedialog.askdirectory(
            title="Choose report output folder",
            initialdir=self.output_folder_var.get(),
        )

        if selected:
            self.output_folder_var.set(selected)

    def get_selected_reports(
        self,
    ) -> list[str]:
        return [
            report_name for report_name, var in self.report_vars.items() if var.get()
        ]

    def get_selected_formats(
        self,
    ) -> list[str]:
        formats: list[str] = []

        if self.csv_var.get():
            formats.append("csv")

        if self.xlsx_var.get():
            formats.append("xlsx")

        if self.pdf_var.get():
            formats.append("pdf")

        return formats

    def generate_selected(
        self,
    ) -> None:
        report_names = self.get_selected_reports()
        formats = self.get_selected_formats()

        if not report_names:
            messagebox.showwarning(
                "No Reports Selected",
                "Select at least one report.",
            )
            return

        if not formats:
            messagebox.showwarning(
                "No Output Format Selected",
                "Select CSV, XLSX, PDF, or any combination.",
            )
            return

        try:
            sharepoint_service = self._get_sharepoint_service()
            move_date = self._selected_move_date()
            file_prefix = build_report_file_prefix(
                self.app_state.release,
                move_date,
            )
            if sharepoint_service is None:
                output_folder = Path(self.output_folder_var.get())
                output_folder.mkdir(parents=True, exist_ok=True)
                archive_matching_reports(
                    output_folder,
                    file_prefix,
                )
            else:
                output_folder = sharepoint_service.prepare_release_folder(
                    self.app_state.release,
                    file_prefix=file_prefix,
                )
        except (OSError, PermissionError, ValueError) as exc:
            messagebox.showerror(
                "Report Destination Error",
                str(exc),
            )
            return

        total_steps = len(report_names) * len(formats)
        completed_steps = 0
        generated_files: list[Path] = []

        self.progress_bar.set(0)
        self.set_results_text("")

        for report_name in report_names:
            for output_format in formats:
                self.current_report_var.set(
                    f"Generating {report_name} ({output_format.upper()})..."
                )
                self.update_idletasks()

                try:
                    output_path = self.report_registry.generate(
                        name=report_name,
                        output_format=output_format,
                        state=self.app_state,
                        output_folder=output_folder,
                        include_empty=self.include_empty_var.get(),
                    )

                    if output_path is not None:
                        generated_files.append(output_path)

                except NotImplementedError:
                    # Some reports may not support PDF yet.
                    pass
                except PermissionError as exc:
                    messagebox.showerror(
                        "Report File In Use",
                        str(exc),
                    )
                    return

                completed_steps += 1
                self.progress_bar.set(completed_steps / total_steps)
                self.update_idletasks()

        self.current_report_var.set("Complete")
        if sharepoint_service is not None:
            generated_files = sharepoint_service.timestamp_files(
                generated_files,
                self.app_state.release,
                move_date=move_date,
            )
        else:
            generated_files = prefix_report_files(
                generated_files,
                file_prefix,
            )

        if generated_files:
            result_text = "Generated:\n" + "\n".join(
                f"- {path.name}" for path in generated_files
            )
        else:
            result_text = "No report files were generated."

        self.set_results_text(result_text)

    def generate_forecast(
        self,
    ) -> None:
        if self.context is None:
            messagebox.showerror(
                "Forecast Error",
                "Forecast generation is not available without application context.",
            )
            return

        service = ForecastService(
            context=self.context,
            report_registry=self.report_registry,
        )

        formats = service.get_enabled_formats()
        if not formats:
            messagebox.showwarning(
                "No Forecast Formats Enabled",
                "Enable at least one format in settings.json reports.forecast_formats.",
            )
            return

        report_names = service.get_enabled_report_names()
        if not report_names:
            messagebox.showwarning(
                "No Forecast Reports Enabled",
                "Enable at least one report in settings.json reports.forecast_reports.",
            )
            return

        self.progress_bar.set(0)
        self.current_report_var.set("Generating 3 month forecast...")
        self.set_results_text("")
        self.update_idletasks()

        try:
            sharepoint_service = self._get_sharepoint_service()
            results = service.generate_forecast(
                base_output_folder=(
                    sharepoint_service.root
                    if sharepoint_service is not None
                    else self.base_output_folder
                ),
                formats=formats,
                include_empty=self.include_empty_var.get(),
            )
            if sharepoint_service is not None:
                for result in results:
                    result.generated_files[:] = sharepoint_service.timestamp_files(
                        result.generated_files,
                        result.release,
                    )
        except (OSError, PermissionError, ValueError) as exc:
            messagebox.showerror(
                "Report File In Use",
                str(exc),
            )
            return

        self.progress_bar.set(1)
        self.current_report_var.set("Forecast Complete")

        generated_files = [
            path for result in results for path in result.generated_files
        ]

        if generated_files:
            self.set_results_text(
                "Forecast generated:\n"
                + "\n".join(
                    f"{result.release} {result.mode}: {len(result.generated_files)} files"
                    for result in results
                )
            )
        else:
            self.set_results_text("No forecast report files were generated.")

    def generate_inventory_forecast(
        self,
    ) -> None:
        if self.context is None:
            messagebox.showerror(
                "Inventory Forecast Error",
                "Inventory forecast generation requires application context.",
            )
            return

        formats = self.get_selected_formats()
        if not formats:
            messagebox.showwarning(
                "No Output Format Selected",
                "Select CSV, XLSX, PDF, or any combination.",
            )
            return

        try:
            sharepoint_service = self._get_sharepoint_service()
        except ValueError as exc:
            messagebox.showerror("Report Destination Error", str(exc))
            return

        output_root = (
            sharepoint_service.root
            if sharepoint_service is not None
            else self.base_output_folder
        )
        output_folder = (
            output_root / "Inventory Issues Forecast" / date.today().isoformat()
        )
        output_folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        try:
            archive_existing_reports(output_folder)
        except PermissionError as exc:
            messagebox.showerror(
                "Report File In Use",
                str(exc),
            )
            return

        self.progress_bar.set(0)
        self.current_report_var.set("Generating inventory issues forecast...")
        self.set_results_text("")
        self.update_idletasks()

        try:
            generated_files = InventoryForecastService(
                context=self.context,
            ).generate(
                output_folder=output_folder,
                formats=formats,
            )
            if sharepoint_service is not None:
                generated_files = sharepoint_service.timestamp_files(
                    generated_files,
                    "Inventory Issues Forecast",
                )
        except PermissionError as exc:
            messagebox.showerror(
                "Report File In Use",
                str(exc),
            )
            return

        self.progress_bar.set(1)
        self.current_report_var.set("Inventory Forecast Complete")
        self.set_results_text(
            "Inventory issues forecast generated:\n"
            + "\n".join(f"- {path.name}" for path in generated_files)
        )

    def generate_after_action(
        self,
    ) -> None:
        if self.context is None:
            messagebox.showerror(
                "After Action Error",
                "After-action generation requires application context.",
            )
            return

        formats = self.get_selected_formats()
        if not formats:
            messagebox.showwarning(
                "No Output Format Selected",
                "Select CSV, XLSX, PDF, or any combination.",
            )
            return

        try:
            selected_date = datetime.strptime(
                self.after_action_date_var.get().strip(),
                "%Y-%m-%d",
            ).date()
        except ValueError:
            messagebox.showwarning(
                "Invalid Date",
                "Enter the after-action date as YYYY-MM-DD.",
            )
            return

        if selected_date >= date.today():
            messagebox.showwarning(
                "Date Not Passed",
                "After-action reports require a date before today.",
            )
            return

        try:
            sharepoint_service = self._get_sharepoint_service()
        except ValueError as exc:
            messagebox.showerror("Report Destination Error", str(exc))
            return

        output_root = (
            sharepoint_service.root
            if sharepoint_service is not None
            else self.base_output_folder
        )
        output_folder = (
            output_root / "After Action" / safe_release_name(selected_date.isoformat())
        )

        self.progress_bar.set(0)
        self.current_report_var.set("Generating after-action report...")
        self.set_results_text("")
        self.update_idletasks()

        try:
            generated_files = AfterActionService(
                context=self.context,
            ).generate(
                selected_date=selected_date,
                output_folder=output_folder,
                formats=formats,
            )
            if sharepoint_service is not None:
                generated_files = sharepoint_service.timestamp_files(
                    generated_files,
                    f"After Action {selected_date.isoformat()}",
                )
        except PermissionError as exc:
            messagebox.showerror(
                "Report File In Use",
                str(exc),
            )
            return

        self.progress_bar.set(1)
        self.current_report_var.set("After Action Complete")
        self.set_results_text(
            "After-action report generated:\n"
            + "\n".join(f"- {path.name}" for path in generated_files)
        )

    def set_results_text(
        self,
        text: str,
    ) -> None:
        self.results_textbox.configure(state="normal")
        self.results_textbox.delete("1.0", "end")
        self.results_textbox.insert("1.0", text)
        self.results_textbox.configure(state="disabled")

    def _get_sharepoint_service(
        self,
    ) -> SharePointReportService | None:
        if self.destination_var.get() != "sharepoint":
            return None
        if self.context is None:
            raise ValueError("SharePoint output requires application context.")

        url = str(
            self.context.settings.get("reports", {}).get("sharepoint_url", "")
        ).strip()
        if not url:
            raise ValueError(
                "Set reports.sharepoint_url in settings.json before using SharePoint."
            )
        return SharePointReportService(url)

    def _selected_move_date(
        self,
    ) -> str:
        selected_dates = {
            self.app_state.effort_dates.get(effort_id, "").strip()
            for effort_id in self.app_state.selected_effort_ids
            if self.app_state.effort_dates.get(effort_id, "").strip()
        }

        if not selected_dates:
            selected_dates = {
                str(value).strip()
                for value in self.app_state.effort_dates.values()
                if str(value).strip()
            }

        if not selected_dates:
            return "Unknown"

        return sorted(selected_dates)[0]
