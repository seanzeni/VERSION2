from __future__ import annotations

# Purpose:
#     Export selected visible elements to fixed-width mainframe format.
#
# Used By:
#     MainWindow
#
# Responsibilities:
#     - Sort selected export rows alphabetically by element name.
#     - Build fixed-width export records.
#     - Write export file.
#
# Notes:
#     This file should not apply validation rules.
#     Validation already happened before export.

from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.formatter import build_record
from app.core.models import Element
from app.reports.report_utils import get_release_mode_date_folder
from app.reports.report_utils import make_read_only
from app.reports.report_utils import make_writable


class Exporter:
    def __init__(
        self,
        settings: dict[str, Any],
        base_dir: str | Path,
    ) -> None:
        self.settings = settings
        self.base_dir = Path(base_dir)

    def sort_elements(
        self,
        elements: list[Element],
    ) -> list[Element]:
        return sorted(
            elements,
            key=lambda element: element.element.upper(),
        )

    def build_lines(
        self,
        elements: list[Element],
        mode: str,
    ) -> list[str]:
        selected_elements = [
            element for element in elements if element.visible and element.selected
        ]

        return [
            build_record(
                source_row=element.source_row,
                mode=mode,
            )
            for element in self.sort_elements(selected_elements)
        ]

    def build_default_output_path(
        self,
        release: str,
        mode: str,
        move_date: str | object | None,
    ) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_folder = self.base_dir / str(
            self.settings.get(
                "files",
                {},
            ).get(
                "default_output_folder",
                "Output",
            )
        )

        return get_release_mode_date_folder(
            release=release,
            mode=mode,
            move_date=move_date,
            base_path=output_folder,
        ) / f"{release}_export_{timestamp}.txt"

    def build_labeled_output_path(
        self,
        output_path: str | Path,
        label: str,
    ) -> Path:
        path = Path(output_path)
        clean_label = str(label).strip().upper()
        export_marker = "_export_"

        if export_marker in path.stem:
            stem = path.stem.replace(
                export_marker,
                f"_{clean_label}{export_marker}",
                1,
            )
        else:
            stem = f"{path.stem}_{clean_label}"

        return path.with_name(f"{stem}{path.suffix}")

    def export(
        self,
        elements: list[Element],
        mode: str,
        release: str,
        output_path: str | Path | None = None,
        move_date: str | object | None = None,
    ) -> Path:
        path = (
            Path(output_path)
            if output_path is not None
            else self.build_default_output_path(
                release=release,
                mode=mode,
                move_date=move_date,
            )
        )

        lines = self.build_lines(
            elements=elements,
            mode=mode,
        )

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        make_writable(path)

        with path.open(
            "w",
            encoding="utf-8",
        ) as file:
            file.write("\n".join(lines))

        make_read_only(path)

        return path
