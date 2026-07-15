from __future__ import annotations

# Purpose:
#     Standalone previous-day NDVR movement audit.
#
# Usage:
#     py -3.14 scripts/ndvr_daily_move_audit.py
#     py -3.14 scripts/ndvr_daily_move_audit.py --date 2026-07-14

import argparse
import sys
from collections import Counter
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
from app.core.release_rules import mode_date  # noqa: E402
from app.reports.pdf_utils import build_table  # noqa: E402
from app.reports.pdf_utils import heading  # noqa: E402
from app.reports.pdf_utils import spacer  # noqa: E402
from app.reports.pdf_utils import write_pdf  # noqa: E402
from app.reports.report_utils import export_xlsx  # noqa: E402
from app.reports.report_utils import safe_release_name  # noqa: E402
from app.services.data_loader import DataLoader  # noqa: E402
from app.services.db_service import DBService  # noqa: E402
from app.services.mainframe_location_service import MainframeLocationService  # noqa: E402


TARGET_ENVS = {"QUAL1", "PROD1"}
TARGET_SYSTEMS = {"PRIVATE1", "SHARED01"}
NDVR_PATTERNS = ("*.txt", "*.dat", "*.csv")

DETAIL_HEADERS = [
    "Status",
    "Move Date",
    "Mode",
    "Env",
    "System",
    "Subsystem",
    "Element",
    "Type",
    "NDVR Package",
    "NDVR RC",
    "NDVR Time",
    "Inventory Release",
    "Project",
    "Expected Move Dates",
    "Reason",
    "Source File",
]

SUMMARY_HEADERS = ["Status", "Count"]


@dataclass(frozen=True, slots=True)
class InventoryRow:
    release: str
    project: str
    element: str
    type: str


@dataclass(frozen=True, slots=True)
class AuthorizationResult:
    status: str
    release: str = ""
    project: str = ""
    expected_dates: str = ""
    reason: str = ""


@dataclass(frozen=True, slots=True)
class AuditRecord:
    record: MainframeLocationRecord
    source_file: Path


class DailyMoveAudit:
    def __init__(
        self,
        settings: dict[str, Any],
        base_dir: Path,
        inventory_file: Path | None = None,
        ndvr_source: Path | None = None,
        output_folder: Path | None = None,
        db_service: DBService | None = None,
    ) -> None:
        self.settings = settings
        self.base_dir = base_dir
        self.inventory_file = self._resolve_path(
            inventory_file or settings["files"]["default_input_file"]
        )
        self.ndvr_source = self._resolve_path(
            ndvr_source or settings["files"]["default_ndvr_file"]
        )
        self.output_folder = self._resolve_path(
            output_folder
            or settings["files"].get(
                "default_output_folder",
                "Output",
            )
        )
        self.db_service = db_service or DBService(settings["database"])
        self._effort_cache: dict[str, Any] = {}

    def run(
        self,
        target_date: date,
    ) -> list[Path]:
        rows = self.build_rows(target_date)
        output_folder = (
            self.output_folder
            / "NDVR Daily Move Audit"
            / safe_release_name(target_date.isoformat())
        )
        output_folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        xlsx_path = output_folder / f"NDVR_Daily_Move_Audit_{target_date:%Y%m%d}.xlsx"
        pdf_path = output_folder / f"NDVR_Daily_Move_Audit_{target_date:%Y%m%d}.pdf"

        export_xlsx(
            output_path=xlsx_path,
            sheets={
                "Summary": (
                    SUMMARY_HEADERS,
                    self._summary_rows(rows),
                ),
                "Detail": (
                    DETAIL_HEADERS,
                    rows or self._empty_rows(target_date),
                ),
            },
        )
        self._export_pdf(
            output_path=pdf_path,
            target_date=target_date,
            rows=rows,
        )
        return [xlsx_path, pdf_path]

    def build_rows(
        self,
        target_date: date,
    ) -> list[list[object]]:
        inventory_lookup = self._build_inventory_lookup()
        audit_records = self._load_target_ndvr_records(target_date)

        rows: list[list[object]] = []
        for audit_record in sorted(
            audit_records,
            key=lambda item: (
                item.record.env,
                item.record.system,
                item.record.subsystem,
                item.record.element,
                item.record.type,
                item.record.time_generated,
            ),
        ):
            record = audit_record.record
            mode = "PROD" if record.env.upper() == "PROD1" else "QUAL"
            authorization = self._authorize(
                record=record,
                mode=mode,
                target_date=target_date,
                inventory_rows=inventory_lookup.get(record.key, []),
            )
            rows.append(
                [
                    authorization.status,
                    target_date.isoformat(),
                    mode,
                    record.env,
                    record.system,
                    record.subsystem,
                    record.element,
                    record.type,
                    record.ndvr_package,
                    f"{record.ndvr_rc:05d}" if record.ndvr_rc is not None else "",
                    record.time_generated,
                    authorization.release,
                    authorization.project,
                    authorization.expected_dates,
                    authorization.reason,
                    audit_record.source_file.name,
                ]
            )

        return rows

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

    def _load_target_ndvr_records(
        self,
        target_date: date,
    ) -> list[AuditRecord]:
        records_by_key: dict[tuple[str, ...], AuditRecord] = {}

        for file_path in self._ndvr_files():
            service = MainframeLocationService().load_file(file_path)
            for record in service.records:
                if not self._is_target_record(record, target_date):
                    continue

                records_by_key.setdefault(
                    self._record_key(record),
                    AuditRecord(
                        record=record,
                        source_file=file_path,
                    ),
                )

        return list(records_by_key.values())

    def _ndvr_files(
        self,
    ) -> list[Path]:
        source = self.ndvr_source
        folder = source.parent if source.is_file() else source

        if not folder.exists():
            raise FileNotFoundError(f"NDVR source was not found: {folder}")

        if not folder.is_dir():
            raise NotADirectoryError(f"NDVR source is not a directory: {folder}")

        files = {
            file_path
            for pattern in NDVR_PATTERNS
            for file_path in folder.glob(pattern)
            if file_path.is_file()
        }

        return sorted(
            files,
            key=lambda file_path: (
                file_path.stat().st_mtime,
                file_path.name,
            ),
            reverse=True,
        )

    def _is_target_record(
        self,
        record: MainframeLocationRecord,
        target_date: date,
    ) -> bool:
        return (
            coerce_date(record.date_generated) == target_date
            and record.env.strip().upper() in TARGET_ENVS
            and record.system.strip().upper() in TARGET_SYSTEMS
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
        )

    def _authorize(
        self,
        record: MainframeLocationRecord,
        mode: str,
        target_date: date,
        inventory_rows: list[InventoryRow],
    ) -> AuthorizationResult:
        if not inventory_rows:
            return AuthorizationResult(
                status="NOT_TRACKED_IN_INVENTORY",
                reason=(
                    "Element/type moved in NDVR but was not found in the "
                    "inventory file."
                ),
            )

        expected_dates: list[str] = []

        for inventory_row in inventory_rows:
            effort = self._find_effort(
                release=inventory_row.release,
                project=inventory_row.project,
            )
            expected_date = mode_date(effort, mode) if effort is not None else None
            if expected_date is not None:
                expected_dates.append(
                    f"{inventory_row.release} / {inventory_row.project}: "
                    f"{mode} {expected_date.isoformat()}"
                )

            if expected_date == target_date:
                return AuthorizationResult(
                    status="APPROVED_MOVE",
                    release=inventory_row.release,
                    project=inventory_row.project,
                    expected_dates="; ".join(sorted(set(expected_dates))),
                    reason=(
                        f"Inventory project was authorized for {mode} movement "
                        f"on {target_date.isoformat()}."
                    ),
                )

        return AuthorizationResult(
            status="TRACKED_NOT_AUTHORIZED_FOR_DATE",
            release=", ".join(sorted({row.release for row in inventory_rows})),
            project=", ".join(sorted({row.project for row in inventory_rows})),
            expected_dates="; ".join(sorted(set(expected_dates))) or "No SQL date found",
            reason=(
                "Element/type was tracked in inventory, but no matching project "
                f"was authorized for {mode} movement on {target_date.isoformat()}."
            ),
        )

    def _find_effort(
        self,
        release: str,
        project: str,
    ):
        if release not in self._effort_cache:
            self._effort_cache[release] = {
                effort.effort_id.strip().upper(): effort
                for effort in self.db_service.get_efforts_for_release(release)
            }

        return self._effort_cache[release].get(project.strip().upper())

    def _summary_rows(
        self,
        rows: list[list[object]],
    ) -> list[list[object]]:
        counts = Counter(str(row[0]) for row in rows)
        if not counts:
            return [["NO_MOVES_FOUND", 0]]

        return [
            [
                status,
                count,
            ]
            for status, count in sorted(counts.items())
        ]

    def _empty_rows(
        self,
        target_date: date,
    ) -> list[list[object]]:
        return [
            [
                "NO_MOVES_FOUND",
                target_date.isoformat(),
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
                "No matching NDVR moves were found.",
                "",
            ]
        ]

    def _export_pdf(
        self,
        output_path: Path,
        target_date: date,
        rows: list[list[object]],
    ) -> Path:
        story = [
            heading("NDVR Daily Move Audit"),
            spacer(),
            build_table(
                headers=["Move Date"],
                rows=[[target_date.isoformat()]],
                column_widths=[2.0 * 72],
            ),
            spacer(),
            build_table(
                headers=SUMMARY_HEADERS,
                rows=self._summary_rows(rows),
                column_widths=[3.0 * 72, 1.0 * 72],
            ),
            spacer(),
            build_table(
                headers=DETAIL_HEADERS,
                rows=rows or self._empty_rows(target_date),
            ),
        ]
        return write_pdf(output_path, story, use_landscape=True)

    def _resolve_path(
        self,
        value: str | Path,
    ) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return self.base_dir / path


def parse_args(
    argv: list[str] | None = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a daily NDVR move audit report."
    )
    parser.add_argument(
        "--settings",
        default=str(REPO_ROOT / "settings.json"),
        help="Path to settings.json. Defaults to the repository settings file.",
    )
    parser.add_argument(
        "--date",
        help="Audit date in YYYY-MM-DD format. Defaults to previous calendar day.",
    )
    parser.add_argument(
        "--ndvr-source",
        help="Optional NDVR source directory or file. Defaults to settings.",
    )
    parser.add_argument(
        "--inventory-file",
        help="Optional inventory spreadsheet path. Defaults to settings.",
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

    generated_files = DailyMoveAudit(
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
