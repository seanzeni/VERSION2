from __future__ import annotations

# Purpose:
#     Standalone TO QUAL / TO PROD movement reports from NDVR history.
#
# Usage:
#     py -3.14 scripts/to_environment_report.py --date 2026-07-14

import argparse
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.config.settings_loader import SettingsLoader  # noqa: E402
from app.core.models import MainframeLocationRecord  # noqa: E402
from app.core.release_rules import coerce_date  # noqa: E402
from app.reports.pdf_utils import build_table  # noqa: E402
from app.reports.pdf_utils import heading  # noqa: E402
from app.reports.pdf_utils import spacer  # noqa: E402
from app.reports.pdf_utils import write_pdf  # noqa: E402
from app.reports.report_utils import export_xlsx  # noqa: E402
from app.services.data_loader import DataLoader  # noqa: E402
from app.services.mainframe_location_service import MainframeLocationService  # noqa: E402
from scripts.report_script_utils import iter_ndvr_files  # noqa: E402
from scripts.report_script_utils import resolve_path  # noqa: E402


REPORTS = {
    "QUAL": "QUAL1",
    "PROD": "PROD1",
}

DETAIL_HEADERS = [
    "Move Date",
    "Report",
    "Env",
    "System",
    "Subsystem",
    "Element",
    "Type",
    "Version",
    "CCID",
    "NDVR Package",
    "NDVR RC",
    "NDVR Time",
    "User",
    "Inventory Release",
    "Project",
    "Association",
    "Source File",
]


@dataclass(frozen=True, slots=True)
class InventoryRow:
    release: str
    project: str
    element: str
    type: str


@dataclass(frozen=True, slots=True)
class MovementRecord:
    record: MainframeLocationRecord
    source_file: Path


@dataclass(frozen=True, slots=True)
class Association:
    release: str = ""
    project: str = ""
    detail: str = "Not associated to release."


class ToEnvironmentReport:
    def __init__(
        self,
        settings: dict[str, Any],
        base_dir: Path,
        inventory_file: Path | None = None,
        ndvr_source: Path | None = None,
        output_folder: Path | None = None,
    ) -> None:
        self.settings = settings
        self.base_dir = base_dir
        self.inventory_file = resolve_path(
            inventory_file or settings["files"]["default_input_file"],
            base_dir,
        )
        self.ndvr_source = resolve_path(
            ndvr_source or settings["files"]["default_ndvr_file"],
            base_dir,
        )
        self.output_folder = resolve_path(
            output_folder
            or settings["files"].get(
                "default_output_folder",
                "Output",
            ),
            base_dir,
        )

    def run(
        self,
        target_date: date,
    ) -> list[Path]:
        rows_by_report = self.build_rows(target_date)
        generated_files: list[Path] = []

        for report_name, rows in rows_by_report.items():
            report_folder = self.output_folder / f"TO {report_name}"
            report_folder.mkdir(
                parents=True,
                exist_ok=True,
            )
            date_text = target_date.strftime("%Y%m%d")
            stem = f"TO_{report_name}_{date_text}"
            xlsx_path = report_folder / f"{stem}.xlsx"
            pdf_path = report_folder / f"{stem}.pdf"

            export_xlsx(
                output_path=xlsx_path,
                sheets={
                    f"TO {report_name}": (
                        DETAIL_HEADERS,
                        rows or self._empty_rows(target_date, report_name),
                    )
                },
            )
            self._export_pdf(
                output_path=pdf_path,
                target_date=target_date,
                report_name=report_name,
                rows=rows,
            )
            generated_files.extend([xlsx_path, pdf_path])

        return generated_files

    def build_rows(
        self,
        target_date: date,
    ) -> dict[str, list[list[object]]]:
        inventory_lookup = self._build_inventory_lookup()
        rows_by_report: dict[str, list[list[object]]] = {
            report_name: []
            for report_name in REPORTS
        }

        for movement in self._load_movements(target_date):
            record = movement.record
            report_name = "PROD" if record.env.strip().upper() == "PROD1" else "QUAL"
            association = self._associate(
                record=record,
                inventory_rows=inventory_lookup.get(record.key, []),
            )
            rows_by_report[report_name].append(
                [
                    target_date.isoformat(),
                    f"TO {report_name}",
                    record.env,
                    record.system,
                    record.subsystem,
                    record.element,
                    record.type,
                    record.version,
                    record.ccid,
                    record.ndvr_package,
                    f"{record.ndvr_rc:05d}" if record.ndvr_rc is not None else "",
                    record.time_generated,
                    record.user,
                    association.release,
                    association.project,
                    association.detail,
                    movement.source_file.name,
                ]
            )

        for rows in rows_by_report.values():
            rows.sort(
                key=lambda row: (
                    str(row[3]).upper(),
                    str(row[4]).upper(),
                    str(row[5]).upper(),
                    str(row[6]).upper(),
                    str(row[11]),
                )
            )

        return rows_by_report

    def _build_inventory_lookup(
        self,
    ) -> dict[tuple[str, str], list[InventoryRow]]:
        data_loader = DataLoader(
            file_path=self.inventory_file,
            required_columns=self.settings["required_columns"],
        )
        dataframe = data_loader.load()
        lookup: dict[tuple[str, str], list[InventoryRow]] = defaultdict(list)

        for _, row in dataframe.iterrows():
            inventory_row = InventoryRow(
                release=str(row.get("Release", "")).strip(),
                project=str(row.get("Project", "")).strip(),
                element=str(row.get("Element", "")).strip(),
                type=str(row.get("Type", "")).strip(),
            )
            if not inventory_row.element or not inventory_row.type:
                continue
            lookup[
                (
                    inventory_row.element.upper(),
                    inventory_row.type.upper(),
                )
            ].append(inventory_row)

        return dict(lookup)

    def _load_movements(
        self,
        target_date: date,
    ) -> list[MovementRecord]:
        records_by_key: dict[tuple[str, ...], MovementRecord] = {}

        for file_path in iter_ndvr_files(self.ndvr_source, self.base_dir):
            service = MainframeLocationService().load_file(file_path)
            for record in service.records:
                if not self._is_target_record(record, target_date):
                    continue
                records_by_key.setdefault(
                    self._record_key(record),
                    MovementRecord(
                        record=record,
                        source_file=file_path,
                    ),
                )

        return list(records_by_key.values())

    def _is_target_record(
        self,
        record: MainframeLocationRecord,
        target_date: date,
    ) -> bool:
        return (
            coerce_date(record.date_generated) == target_date
            and record.env.strip().upper() in REPORTS.values()
        )

    def _record_key(
        self,
        record: MainframeLocationRecord,
    ) -> tuple[str, ...]:
        return (
            record.element.upper(),
            record.type.upper(),
            record.env.upper(),
            record.system.upper(),
            record.subsystem.upper(),
            record.date_generated,
            record.time_generated,
            record.ndvr_package.upper(),
            record.ccid.upper(),
        )

    def _associate(
        self,
        record: MainframeLocationRecord,
        inventory_rows: list[InventoryRow],
    ) -> Association:
        if not inventory_rows:
            return Association()

        package = str(record.ndvr_package).strip().upper()
        ccid = str(record.ccid).strip().upper()

        for inventory_row in inventory_rows:
            project = inventory_row.project.strip().upper()
            if project and package and (
                project.startswith(package) or package.startswith(project)
            ):
                return Association(
                    release=inventory_row.release,
                    project=inventory_row.project,
                    detail="Linked by inventory project and NDVR package.",
                )

        for inventory_row in inventory_rows:
            project = inventory_row.project.strip().upper()
            if project and ccid and (project.startswith(ccid) or ccid.startswith(project)):
                return Association(
                    release=inventory_row.release,
                    project=inventory_row.project,
                    detail="Assumption: linked based off CCID.",
                )

        releases = ", ".join(sorted({row.release for row in inventory_rows if row.release}))
        projects = ", ".join(sorted({row.project for row in inventory_rows if row.project}))
        return Association(
            release=releases,
            project=projects,
            detail="Linked by element/type in inventory.",
        )

    def _empty_rows(
        self,
        target_date: date,
        report_name: str,
    ) -> list[list[object]]:
        return [
            [
                target_date.isoformat(),
                f"TO {report_name}",
                REPORTS[report_name],
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "No matching NDVR moves found.",
                "",
            ]
        ]

    def _export_pdf(
        self,
        output_path: Path,
        target_date: date,
        report_name: str,
        rows: list[list[object]],
    ) -> Path:
        story = [
            heading(f"TO {report_name}"),
            spacer(),
            build_table(
                headers=["Move Date", "Rows"],
                rows=[[target_date.isoformat(), len(rows)]],
                column_widths=[2.0 * 72, 1.0 * 72],
            ),
            spacer(),
            build_table(
                headers=DETAIL_HEADERS,
                rows=rows or self._empty_rows(target_date, report_name),
            ),
        ]
        return write_pdf(output_path, story, use_landscape=True)


def parse_args(
    argv: list[str] | None = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create TO QUAL and TO PROD NDVR movement reports."
    )
    parser.add_argument(
        "--settings",
        default=str(REPO_ROOT / "settings.json"),
        help="Path to settings.json. Defaults to the repository settings file.",
    )
    parser.add_argument(
        "--date",
        help="Move date in YYYY-MM-DD format. Defaults to previous calendar day.",
    )
    parser.add_argument(
        "--inventory-file",
        help="Optional inventory spreadsheet path. Defaults to settings.",
    )
    parser.add_argument(
        "--ndvr-source",
        help="Optional NDVR source directory or file. Defaults to settings.",
    )
    parser.add_argument(
        "--output-folder",
        help="Optional output folder. Defaults to settings.",
    )
    return parser.parse_args(argv)


def parse_target_date(
    value: str | None,
    today: date | None = None,
) -> date:
    if not value:
        return (today or date.today()) - timedelta(days=1)

    return datetime.strptime(value, "%Y-%m-%d").date()


def main(
    argv: list[str] | None = None,
) -> int:
    args = parse_args(argv)
    settings_path = Path(args.settings).resolve()
    settings = SettingsLoader(settings_path).load()
    base_dir = settings_path.parent
    target_date = parse_target_date(args.date)

    generated_files = ToEnvironmentReport(
        settings=settings,
        base_dir=base_dir,
        inventory_file=Path(args.inventory_file) if args.inventory_file else None,
        ndvr_source=Path(args.ndvr_source) if args.ndvr_source else None,
        output_folder=Path(args.output_folder) if args.output_folder else None,
    ).run(target_date)

    print("Generated:")
    for file_path in generated_files:
        print(f"- {file_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
