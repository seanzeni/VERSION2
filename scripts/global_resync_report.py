from __future__ import annotations

# Purpose:
#     Standalone global NDVR resync report across all lifecycle environments.
#
# Usage:
#     py -3.14 scripts/global_resync_report.py

import argparse
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.config.settings_loader import SettingsLoader  # noqa: E402
from app.core.models import MainframeLocationRecord  # noqa: E402
from app.reports.report_utils import export_xlsx  # noqa: E402
from app.services.mainframe_location_service import MainframeLocationService  # noqa: E402
from scripts.report_script_utils import latest_ndvr_file  # noqa: E402
from scripts.report_script_utils import resolve_path  # noqa: E402


DETAIL_HEADERS = [
    "Element",
    "Type",
    "Target Env",
    "Target Level",
    "Target System",
    "Target Subsystem",
    "Target Version",
    "Target CCID",
    "Newer Source Env",
    "Newer Source Level",
    "Newer Source System",
    "Newer Source Subsystem",
    "Newer Source Version",
    "Newer Source CCID",
    "Reason",
]


class GlobalResyncReport:
    FILE_NAME = "Global_Resync_Report.xlsx"

    def __init__(
        self,
        settings: dict[str, Any],
        base_dir: Path,
        ndvr_source: Path | None = None,
        output_folder: Path | None = None,
    ) -> None:
        self.settings = settings
        self.base_dir = base_dir
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
    ) -> list[Path]:
        ndvr_file = latest_ndvr_file(
            self.ndvr_source,
            self.base_dir,
        )
        location_service = MainframeLocationService().load_file(ndvr_file)
        rows = self.build_rows(location_service)

        output_folder = self.output_folder / "Global Resync Report"
        output_path = output_folder / self.FILE_NAME
        export_xlsx(
            output_path=output_path,
            sheets={
                "Global Resync": (
                    DETAIL_HEADERS,
                    rows or self._empty_rows(),
                )
            },
        )
        return [output_path]

    def build_rows(
        self,
        location_service: MainframeLocationService,
    ) -> list[list[object]]:
        rows: list[list[object]] = []

        for records in self._records_by_element_type(location_service).values():
            for target_record in records:
                target_level = env_level(target_record.env)
                if target_level == 0:
                    continue

                for source_record in records:
                    if source_record is target_record:
                        continue

                    source_level = env_level(source_record.env)
                    if source_level < target_level:
                        continue

                    if source_record.version_number <= target_record.version_number:
                        continue

                    rows.append(
                        self._row(
                            target_record=target_record,
                            source_record=source_record,
                            target_level=target_level,
                            source_level=source_level,
                        )
                    )

        return sorted(
            rows,
            key=lambda row: (
                str(row[0]).upper(),
                str(row[1]).upper(),
                -int(row[3]),
                str(row[2]).upper(),
                str(row[4]).upper(),
                str(row[8]).upper(),
            ),
        )

    def _records_by_element_type(
        self,
        location_service: MainframeLocationService,
    ) -> dict[tuple[str, str], list[MainframeLocationRecord]]:
        grouped: dict[tuple[str, str], list[MainframeLocationRecord]] = defaultdict(list)

        for record in location_service.records:
            if record.env.strip().upper() not in MainframeLocationService.VERSION_COMPARE_ENVS:
                continue

            grouped[record.key].append(record)

        return dict(grouped)

    def _row(
        self,
        target_record: MainframeLocationRecord,
        source_record: MainframeLocationRecord,
        target_level: int,
        source_level: int,
    ) -> list[object]:
        return [
            target_record.element,
            target_record.type,
            target_record.env,
            target_level,
            target_record.system,
            target_record.subsystem,
            target_record.version,
            target_record.ccid,
            source_record.env,
            source_level,
            source_record.system,
            source_record.subsystem,
            source_record.version,
            source_record.ccid,
            (
                f"{source_record.env} has newer version {source_record.version}; "
                f"{target_record.env} has {target_record.version}."
            ),
        ]

    def _empty_rows(
        self,
    ) -> list[list[object]]:
        return [
            [
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
                "",
                "",
                f"No global resync issues found as of {date.today().isoformat()}.",
            ]
        ]


def env_level(
    env: str,
) -> int:
    return MainframeLocationService.ENV_LEVELS.get(
        str(env).strip().upper(),
        0,
    )


def parse_args(
    argv: list[str] | None = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a global NDVR resync report across all lifecycle environments."
    )
    parser.add_argument(
        "--settings",
        default=str(REPO_ROOT / "settings.json"),
        help="Path to settings.json. Defaults to the repository settings file.",
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


def main(
    argv: list[str] | None = None,
) -> int:
    args = parse_args(argv)
    settings_path = Path(args.settings).resolve()
    settings = SettingsLoader(settings_path).load()
    base_dir = settings_path.parent

    generated_files = GlobalResyncReport(
        settings=settings,
        base_dir=base_dir,
        ndvr_source=Path(args.ndvr_source) if args.ndvr_source else None,
        output_folder=Path(args.output_folder) if args.output_folder else None,
    ).run()

    print("Generated:")
    for file_path in generated_files:
        print(f"- {file_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
