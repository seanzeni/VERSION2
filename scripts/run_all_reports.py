from __future__ import annotations

# Purpose:
#     Run all standalone operational report scripts from one command.
#
# Usage:
#     py -3.14 scripts/run_all_reports.py
#     py -3.14 scripts/run_all_reports.py --date 2026-07-21 --output C:\Reports\Daily

import argparse
import shutil
import sys
import tempfile
from collections.abc import Callable
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
from app.reports.report_utils import get_unique_path  # noqa: E402
from app.reports.report_utils import make_read_only  # noqa: E402
from app.reports.report_utils import make_writable  # noqa: E402
from app.reports.report_utils import safe_release_name  # noqa: E402
from app.services.after_action_service import AfterActionService  # noqa: E402
from scripts.after_action_report import build_context as build_after_action_context  # noqa: E402
from scripts.fixp_daily_compare import FixpDailyCompare  # noqa: E402
from scripts.global_resync_report import GlobalResyncReport  # noqa: E402
from scripts.ndvr_daily_move_audit import DailyMoveAudit  # noqa: E402
from scripts.region_inventory_audit import RegionInventoryAudit  # noqa: E402
from scripts.report_script_utils import resolve_path  # noqa: E402
from scripts.to_environment_report import ToEnvironmentReport  # noqa: E402


@dataclass(frozen=True, slots=True)
class RunnerContext:
    settings: dict[str, Any]
    base_dir: Path
    report_date: date
    date_provided: bool
    output_root: Path | None
    staging_root: Path | None
    inventory_file: Path | None
    ndvr_source: Path | None
    fixp_source: Path | None


@dataclass(frozen=True, slots=True)
class ReportTask:
    name: str
    run: Callable[[RunnerContext], list[Path]]


def parse_args(
    argv: list[str] | None = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run all standalone report scripts."
    )
    parser.add_argument(
        "--settings",
        default=str(REPO_ROOT / "settings.json"),
        help="Path to settings.json. Defaults to the repository settings file.",
    )
    parser.add_argument(
        "--date",
        help=(
            "Report date in YYYY-MM-DD format. Defaults to previous calendar day "
            "for date-driven reports."
        ),
    )
    parser.add_argument(
        "--output",
        help=(
            "Optional folder for a flat XLSX-only output drop. Existing XLSX "
            "files in this folder are moved to History first."
        ),
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
        "--fixp-source",
        help="Optional FIXP source directory. Defaults to settings.",
    )
    return parser.parse_args(argv)


def parse_report_date(
    value: str | None,
    today: date | None = None,
) -> date:
    if not value:
        return (today or date.today()) - timedelta(days=1)

    return datetime.strptime(value, "%Y-%m-%d").date()


def build_tasks() -> list[ReportTask]:
    return [
        ReportTask(
            name="After Action",
            run=run_after_action,
        ),
        ReportTask(
            name="FIXP Daily Compare",
            run=run_fixp_daily_compare,
        ),
        ReportTask(
            name="NDVR Daily Move Audit",
            run=run_ndvr_daily_move_audit,
        ),
        ReportTask(
            name="Global Resync",
            run=run_global_resync,
        ),
        ReportTask(
            name="Region Inventory Audit",
            run=run_region_inventory_audit,
        ),
        ReportTask(
            name="To Environment",
            run=run_to_environment,
        ),
    ]


def run_after_action(
    context: RunnerContext,
) -> list[Path]:
    output_root = active_output_root(context)
    after_action_context = build_after_action_context(
        settings=context.settings,
        base_dir=context.base_dir,
        inventory_file=context.inventory_file,
        ndvr_source=context.ndvr_source,
    )

    return AfterActionService(after_action_context).generate(
        selected_date=context.report_date,
        output_folder=(
            output_root
            / "After Action"
            / safe_release_name(context.report_date.isoformat())
        ),
        formats=active_formats(context),
    )


def run_fixp_daily_compare(
    context: RunnerContext,
) -> list[Path]:
    return FixpDailyCompare(
        settings=context.settings,
        base_dir=context.base_dir,
        fixp_source=context.fixp_source,
        ndvr_source=context.ndvr_source,
        inventory_file=context.inventory_file,
        output_folder=active_output_root(context),
    ).run(context.report_date if context.date_provided else None)


def run_ndvr_daily_move_audit(
    context: RunnerContext,
) -> list[Path]:
    return DailyMoveAudit(
        settings=context.settings,
        base_dir=context.base_dir,
        inventory_file=context.inventory_file,
        ndvr_source=context.ndvr_source,
        output_folder=active_output_root(context),
    ).run(
        target_date=context.report_date,
        formats=active_formats(context),
    )


def run_global_resync(
    context: RunnerContext,
) -> list[Path]:
    return GlobalResyncReport(
        settings=context.settings,
        base_dir=context.base_dir,
        ndvr_source=context.ndvr_source,
        output_folder=active_output_root(context),
    ).run()


def run_region_inventory_audit(
    context: RunnerContext,
) -> list[Path]:
    return RegionInventoryAudit(
        settings=context.settings,
        base_dir=context.base_dir,
        inventory_file=context.inventory_file,
        ndvr_source=context.ndvr_source,
        output_folder=active_output_root(context),
    ).run(today=context.report_date)


def run_to_environment(
    context: RunnerContext,
) -> list[Path]:
    return ToEnvironmentReport(
        settings=context.settings,
        base_dir=context.base_dir,
        inventory_file=context.inventory_file,
        ndvr_source=context.ndvr_source,
        output_folder=active_output_root(context),
    ).run(
        target_date=context.report_date,
        formats=active_formats(context),
    )


def active_output_root(
    context: RunnerContext,
) -> Path:
    if context.staging_root is not None:
        return context.staging_root

    return resolve_path(
        context.settings["files"].get(
            "default_output_folder",
            "Output",
        ),
        context.base_dir,
    )


def active_formats(
    context: RunnerContext,
) -> list[str]:
    if context.output_root is not None:
        return ["xlsx"]

    return ["xlsx", "pdf", "csv"]


def archive_existing_xlsx(
    output_root: Path,
) -> None:
    output_root.mkdir(
        parents=True,
        exist_ok=True,
    )
    history_folder = output_root / "History"
    history_folder.mkdir(
        exist_ok=True,
    )

    for file_path in output_root.glob("*.xlsx"):
        destination = get_unique_path(history_folder / file_path.name)
        make_writable(file_path)
        shutil.move(
            str(file_path),
            str(destination),
        )
        make_read_only(destination)


def publish_xlsx_files(
    generated_files: list[Path],
    output_root: Path,
) -> list[Path]:
    published_files: list[Path] = []

    for file_path in generated_files:
        if file_path.suffix.lower() != ".xlsx":
            continue

        destination = output_root / file_path.name
        if destination.exists():
            destination = get_unique_path(destination)

        shutil.copy2(
            file_path,
            destination,
        )
        make_read_only(destination)
        published_files.append(destination)

    return published_files


def create_context(
    args: argparse.Namespace,
    staging_root: Path | None = None,
) -> RunnerContext:
    settings_path = Path(args.settings).resolve()
    settings = SettingsLoader(settings_path).load()
    base_dir = settings_path.parent

    return RunnerContext(
        settings=settings,
        base_dir=base_dir,
        report_date=parse_report_date(args.date),
        date_provided=bool(args.date),
        output_root=resolve_path(args.output, base_dir) if args.output else None,
        staging_root=staging_root,
        inventory_file=Path(args.inventory_file) if args.inventory_file else None,
        ndvr_source=Path(args.ndvr_source) if args.ndvr_source else None,
        fixp_source=Path(args.fixp_source) if args.fixp_source else None,
    )


def run_all(
    context: RunnerContext,
) -> tuple[list[Path], list[tuple[str, Exception]]]:
    generated_files: list[Path] = []
    errors: list[tuple[str, Exception]] = []

    for task in build_tasks():
        try:
            task_files = task.run(context)
            generated_files.extend(task_files)
            print(f"{task.name}: generated {len(task_files)} file(s)")
            for file_path in task_files:
                print(f"- {file_path}")
        except Exception as exc:
            errors.append(
                (
                    task.name,
                    exc,
                )
            )
            print(f"{task.name}: ERROR {type(exc).__name__}: {exc}", file=sys.stderr)

    return generated_files, errors


def main(
    argv: list[str] | None = None,
) -> int:
    args = parse_args(argv)

    if args.output:
        output_root = resolve_path(
            args.output,
            Path(args.settings).resolve().parent,
        )
        archive_existing_xlsx(output_root)
        with tempfile.TemporaryDirectory(prefix="version2-report-runner-") as temp_dir:
            context = create_context(
                args,
                staging_root=Path(temp_dir),
            )
            generated_files, errors = run_all(context)
            published_files = publish_xlsx_files(
                generated_files=generated_files,
                output_root=output_root,
            )
            print("Published XLSX files:")
            for file_path in published_files:
                print(f"- {file_path}")

        return 1 if errors else 0

    context = create_context(args)
    _generated_files, errors = run_all(context)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
