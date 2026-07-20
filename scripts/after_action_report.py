from __future__ import annotations

# Purpose:
#     Standalone after-action report generation for a selected move date.
#
# Usage:
#     py -3.14 scripts/after_action_report.py --date 2026-07-14

import argparse
import sys
from datetime import date
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.config.settings_loader import SettingsLoader  # noqa: E402
from app.reports.report_utils import safe_release_name  # noqa: E402
from app.services.after_action_service import AfterActionService  # noqa: E402
from app.services.data_loader import DataLoader  # noqa: E402
from app.services.db_service import DBService  # noqa: E402
from app.services.element_service import ElementService  # noqa: E402
from app.services.mainframe_location_service import MainframeLocationService  # noqa: E402
from app.services.status_marker_service import StatusMarkerService  # noqa: E402
from scripts.report_script_utils import latest_ndvr_file  # noqa: E402
from scripts.report_script_utils import resolve_path  # noqa: E402


DEFAULT_FORMATS = ("xlsx", "pdf", "csv")


def parse_args(
    argv: list[str] | None = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create the after-action report for inventory scheduled on a move date."
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
        "--formats",
        nargs="+",
        choices=DEFAULT_FORMATS,
        default=list(DEFAULT_FORMATS),
        help="Report formats to generate. Defaults to xlsx pdf csv.",
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


def build_context(
    settings: dict,
    base_dir: Path,
    inventory_file: Path | None,
    ndvr_source: Path | None,
) -> SimpleNamespace:
    inventory_path = resolve_path(
        inventory_file or settings["files"]["default_input_file"],
        base_dir,
    )
    ndvr_path = latest_ndvr_file(
        ndvr_source or settings["files"]["default_ndvr_file"],
        base_dir,
    )

    data_loader = DataLoader(
        file_path=inventory_path,
        required_columns=settings["required_columns"],
    )
    data_loader.load()

    return SimpleNamespace(
        data_loader=data_loader,
        db_service=DBService(settings["database"]),
        element_service=ElementService(),
        location_service=MainframeLocationService().load_file(ndvr_path),
        status_marker_service=StatusMarkerService(settings["status_markers"]),
    )


def main(
    argv: list[str] | None = None,
) -> int:
    args = parse_args(argv)
    settings_path = Path(args.settings).resolve()
    settings = SettingsLoader(settings_path).load()
    base_dir = settings_path.parent
    target_date = parse_target_date(args.date)
    output_root = resolve_path(
        args.output_folder
        or settings["files"].get(
            "default_output_folder",
            "Output",
        ),
        base_dir,
    )

    context = build_context(
        settings=settings,
        base_dir=base_dir,
        inventory_file=Path(args.inventory_file) if args.inventory_file else None,
        ndvr_source=Path(args.ndvr_source) if args.ndvr_source else None,
    )
    generated_files = AfterActionService(context).generate(
        selected_date=target_date,
        output_folder=output_root / "After Action" / safe_release_name(target_date.isoformat()),
        formats=args.formats,
    )

    print("Generated:")
    for file_path in generated_files:
        print(f"- {file_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
