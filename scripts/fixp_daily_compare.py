from __future__ import annotations

# Purpose:
#     Standalone day-over-day FIXP inventory comparison report.
#
# Usage:
#     py -3.14 scripts/fixp_daily_compare.py
#     py -3.14 scripts/fixp_daily_compare.py --date 2026-07-15

import argparse
import re
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
from app.reports.report_utils import export_xlsx  # noqa: E402
from app.reports.report_utils import safe_release_name  # noqa: E402
from app.services.data_loader import DataLoader  # noqa: E402
from app.services.mainframe_location_service import MainframeLocationService  # noqa: E402


FIXP_FILE_PATTERN = re.compile(
    r"^FIXP-(?P<date>\d{8})_(?P<time>\d{6})\.txt$",
    re.IGNORECASE,
)

DETAIL_HEADERS = [
    "Compare",
    "Stage",
    "System",
    "Subsys",
    "Element",
    "Type",
    "FIXP Date",
    "FIXP CCID",
    "Owner",
    "Inventory",
]


@dataclass(frozen=True, slots=True)
class InventoryReference:
    release: str
    project: str
    team_lead: str

    @property
    def label(self) -> str:
        return "-".join(
            value
            for value in (
                self.release,
                self.project,
                self.team_lead,
            )
            if value
        )


@dataclass(frozen=True, slots=True)
class FixpSnapshotRecord:
    record: MainframeLocationRecord
    file_timestamp: datetime


class FixpDailyCompare:
    def __init__(
        self,
        settings: dict[str, Any],
        base_dir: Path,
        fixp_source: Path | None = None,
        inventory_file: Path | None = None,
        output_folder: Path | None = None,
    ) -> None:
        self.settings = settings
        self.base_dir = base_dir
        fixp_source_value = fixp_source or settings["files"].get(
            "default_fixp_folder",
            "",
        )
        self.fixp_source = (
            self._resolve_path(fixp_source_value)
            if str(fixp_source_value).strip()
            else None
        )
        self.inventory_file = self._resolve_path(
            inventory_file or settings["files"]["default_input_file"]
        )
        self.output_folder = self._resolve_path(
            output_folder
            or settings["files"].get(
                "default_output_folder",
                "Output",
            )
        )

    def run(
        self,
        target_date: date,
    ) -> list[Path]:
        rows = self.build_rows(target_date)
        output_folder = (
            self.output_folder
            / "FIXP Daily Compare"
            / safe_release_name(target_date.isoformat())
        )
        output_folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        xlsx_path = output_folder / f"FIXP_Daily_Compare_{target_date:%Y%m%d}.xlsx"
        export_xlsx(
            output_path=xlsx_path,
            sheets={
                "FIXP Compare": (
                    DETAIL_HEADERS,
                    rows or self._empty_rows(target_date),
                ),
            },
        )
        return [xlsx_path]

    def build_rows(
        self,
        target_date: date,
    ) -> list[list[object]]:
        previous_date = target_date - timedelta(days=1)
        previous_snapshot = self._build_snapshot(previous_date)
        target_snapshot = self._build_snapshot(target_date)
        inventory_lookup = self._build_inventory_lookup()

        rows: list[list[object]] = []
        all_keys = sorted(
            set(previous_snapshot)
            | set(target_snapshot),
        )

        for key in all_keys:
            previous_record = previous_snapshot.get(key)
            target_record = target_snapshot.get(key)

            compare = self._compare(
                previous_record=previous_record,
                target_record=target_record,
            )
            display_record = (
                target_record.record
                if target_record is not None
                else previous_record.record
                if previous_record is not None
                else None
            )

            if display_record is None:
                continue

            inventory = self._format_inventory(
                inventory_lookup.get(display_record.key, [])
            )
            rows.append(
                [
                    compare,
                    display_record.env,
                    display_record.system,
                    display_record.subsystem,
                    display_record.element,
                    display_record.type,
                    self._format_fixp_date(display_record.date_generated),
                    display_record.ccid,
                    display_record.user,
                    inventory,
                ]
            )

        return rows

    def _build_snapshot(
        self,
        target_date: date,
    ) -> dict[tuple[str, str, str, str, str], FixpSnapshotRecord]:
        snapshot: dict[tuple[str, str, str, str, str], FixpSnapshotRecord] = {}

        for file_path, file_timestamp in self._fixp_files_for_date(target_date):
            service = MainframeLocationService().load_file(file_path)
            for record in service.records:
                key = self._record_key(record)
                candidate = FixpSnapshotRecord(
                    record=record,
                    file_timestamp=file_timestamp,
                )
                existing = snapshot.get(key)

                if existing is None or self._is_newer(candidate, existing):
                    snapshot[key] = candidate

        return snapshot

    def _fixp_files_for_date(
        self,
        target_date: date,
    ) -> list[tuple[Path, datetime]]:
        source = self.fixp_source
        if source is None:
            raise FileNotFoundError(
                "FIXP source folder was not configured. Set files.default_fixp_folder "
                "or pass --fixp-source."
            )

        folder = source.parent if source.is_file() else source

        if not folder.exists():
            raise FileNotFoundError(f"FIXP source was not found: {folder}")

        if not folder.is_dir():
            raise NotADirectoryError(f"FIXP source is not a directory: {folder}")

        files: list[tuple[Path, datetime]] = []
        for file_path in folder.glob("FIXP-*.txt"):
            file_timestamp = self._parse_file_timestamp(file_path)
            if file_timestamp is None or file_timestamp.date() != target_date:
                continue

            files.append(
                (
                    file_path,
                    file_timestamp,
                )
            )

        return sorted(
            files,
            key=lambda item: (
                item[1],
                item[0].name,
            ),
        )

    def _parse_file_timestamp(
        self,
        file_path: Path,
    ) -> datetime | None:
        match = FIXP_FILE_PATTERN.match(file_path.name)
        if match is None:
            return None

        return datetime.strptime(
            f"{match.group('date')}{match.group('time')}",
            "%Y%m%d%H%M%S",
        )

    def _build_inventory_lookup(
        self,
    ) -> dict[tuple[str, str], list[InventoryReference]]:
        data_loader = DataLoader(
            file_path=self.inventory_file,
            required_columns=self.settings["required_columns"],
        )
        dataframe = data_loader.load()
        lookup: dict[tuple[str, str], list[InventoryReference]] = defaultdict(list)

        for _, row in dataframe.iterrows():
            element = str(row.get("Element", "")).strip().upper()
            type_ = str(row.get("Type", "")).strip().upper()

            if not element or not type_:
                continue

            lookup[
                (
                    element,
                    type_,
                )
            ].append(
                InventoryReference(
                    release=str(row.get("Release", "")).strip(),
                    project=str(row.get("Project", "")).strip(),
                    team_lead=str(row.get("DSN ID", "")).strip()[:4],
                )
            )

        return dict(lookup)

    def _compare(
        self,
        previous_record: FixpSnapshotRecord | None,
        target_record: FixpSnapshotRecord | None,
    ) -> str:
        if target_record is None:
            return "deleted"

        if previous_record is None:
            return "modified"

        if self._record_signature(previous_record.record) == self._record_signature(
            target_record.record
        ):
            return "no change"

        return "modified"

    def _record_signature(
        self,
        record: MainframeLocationRecord,
    ) -> tuple[str, str, str, str]:
        return (
            record.version.strip().upper(),
            record.ccid.strip().upper(),
            record.user.strip().upper(),
            record.comments.strip().upper(),
        )

    def _record_key(
        self,
        record: MainframeLocationRecord,
    ) -> tuple[str, str, str, str, str]:
        return (
            record.env.strip().upper(),
            record.system.strip().upper(),
            record.subsystem.strip().upper(),
            record.element.strip().upper(),
            record.type.strip().upper(),
        )

    def _is_newer(
        self,
        candidate: FixpSnapshotRecord,
        existing: FixpSnapshotRecord,
    ) -> bool:
        candidate_date = coerce_date(candidate.record.date_generated) or date.min
        existing_date = coerce_date(existing.record.date_generated) or date.min

        return (
            candidate.file_timestamp,
            candidate_date,
            candidate.record.time_generated,
        ) > (
            existing.file_timestamp,
            existing_date,
            existing.record.time_generated,
        )

    def _format_fixp_date(
        self,
        value: str,
    ) -> str:
        parsed_date = coerce_date(value)
        if parsed_date is None:
            return str(value).strip()

        return parsed_date.strftime("%d-%b-%y")

    def _format_inventory(
        self,
        references: list[InventoryReference],
    ) -> str:
        return "; ".join(
            sorted(
                {
                    reference.label
                    for reference in references
                    if reference.label
                }
            )
        )

    def _empty_rows(
        self,
        target_date: date,
    ) -> list[list[object]]:
        return [
            [
                "no change",
                "",
                "",
                "",
                "",
                "",
                target_date.strftime("%d-%b-%y"),
                "",
                "",
                "No FIXP records found for the compared dates.",
            ]
        ]

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
        description="Create a day-over-day FIXP comparison report."
    )
    parser.add_argument(
        "--settings",
        default=str(REPO_ROOT / "settings.json"),
        help="Path to settings.json. Defaults to the repository settings file.",
    )
    parser.add_argument(
        "--date",
        help="Report date in YYYY-MM-DD format. Defaults to previous calendar day.",
    )
    parser.add_argument(
        "--fixp-source",
        help="Optional FIXP source directory. Defaults to files.default_fixp_folder.",
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

    generated_files = FixpDailyCompare(
        settings=settings,
        base_dir=base_dir,
        fixp_source=Path(args.fixp_source) if args.fixp_source else None,
        inventory_file=Path(args.inventory_file) if args.inventory_file else None,
        output_folder=Path(args.output_folder) if args.output_folder else None,
    ).run(target_date)

    print("Generated:")
    for file_path in generated_files:
        print(f"- {file_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
