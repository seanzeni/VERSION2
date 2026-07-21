from __future__ import annotations

# Purpose:
#     Standalone region/system inventory audit using SQL assignments and NDVR.
#
# Usage:
#     py -3.14 scripts/region_inventory_audit.py

import argparse
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.config.settings_loader import SettingsLoader  # noqa: E402
from app.core.models import MainframeLocationRecord  # noqa: E402
from app.reports.report_utils import export_xlsx  # noqa: E402
from app.services.data_loader import DataLoader  # noqa: E402
from app.services.db_service import DBService  # noqa: E402
from app.services.mainframe_location_service import MainframeLocationService  # noqa: E402
from scripts.report_script_utils import latest_ndvr_file  # noqa: E402
from scripts.report_script_utils import resolve_path  # noqa: E402


SUMMARY_HEADERS = [
    "Region/System",
    "Assigned Bundle",
    "Approved Elements Count",
    "Potential Inventory Updates Count",
    "Improper Activity Count",
]

ASSIGNMENT_HEADERS = [
    "Bundle Id",
    "Bundle Sequence",
    "Bundle TestEnvironment",
    "Bundle Prod Imp Date",
    "Region Id",
    "Region Prefix",
    "Misc Region",
    "System",
    "Effort Id",
]

DETAIL_HEADERS = [
    "Status",
    "Severity",
    "Region",
    "System",
    "Assigned Bundle",
    "Element",
    "Type",
    "NDVR CCID",
    "Inventory Effort Id(s)",
    "Approved Effort Id(s)",
    "NDVR Env",
    "NDVR Subsystem",
    "NDVR Version",
    "NDVR Date",
    "NDVR Time",
    "Reason",
]

STATUS_APPROVED = "APPROVED"
STATUS_POTENTIAL_MISSING_INVENTORY = "POTENTIAL_MISSING_INVENTORY"
STATUS_IMPROPER_ACTIVITY = "IMPROPER_ACTIVITY"


@dataclass(frozen=True, slots=True)
class RegionAssignment:
    bundle_id: str
    bundle_sequence: str
    region: str
    system: str
    effort_id: str
    bundle_test_environment: str = ""
    bundle_prod_imp_date: str = ""
    region_id: str = ""
    region_prefix: str = ""

    @property
    def region_system(self) -> str:
        return f"{self.region}/{self.system}"


@dataclass(frozen=True, slots=True)
class RegionAssignmentGroup:
    bundle_id: str
    region: str
    system: str
    effort_ids: tuple[str, ...]

    @property
    def region_system(self) -> str:
        return f"{self.region}/{self.system}"


@dataclass(frozen=True, slots=True)
class InventoryReference:
    release: str
    effort_id: str
    element: str
    type: str


@dataclass(frozen=True, slots=True)
class RegionAuditRow:
    status: str
    severity: str
    region: str
    system: str
    bundle_id: str
    element: str
    type: str
    ndvr_ccid: str
    inventory_effort_ids: tuple[str, ...]
    approved_effort_ids: tuple[str, ...]
    ndvr_env: str
    ndvr_subsystem: str
    ndvr_version: str
    ndvr_date: str
    ndvr_time: str
    reason: str

    def as_list(self) -> list[object]:
        return [
            self.status,
            self.severity,
            self.region,
            self.system,
            self.bundle_id,
            self.element,
            self.type,
            self.ndvr_ccid,
            "; ".join(self.inventory_effort_ids),
            "; ".join(self.approved_effort_ids),
            self.ndvr_env,
            self.ndvr_subsystem,
            self.ndvr_version,
            self.ndvr_date,
            self.ndvr_time,
            self.reason,
        ]


class SqlRegionAssignmentClient:
    def __init__(
        self,
        db_service: DBService,
    ) -> None:
        self.db_service = db_service

    def load_region_assignments(
        self,
        start_date: date,
        end_date: date,
    ) -> list[RegionAssignment]:
        query = """
        SELECT
            b.Id AS BundleId,
            CAST(b.Sequence AS VARCHAR(50)) AS BundleSequence,
            CAST(b.TestEnvironment AS VARCHAR(50)) AS BundleTestEnvironment,
            b.BundleProdImpDate AS BundleProdImpDate,
            r.Id AS RegionId,
            LEFT(LTRIM(RTRIM(r.Id)), 3) AS RegionPrefix,
            mes.Region AS Region,
            mes.System AS System,
            e.Id AS EffortId
        FROM Bundles b
        INNER JOIN Efforts e
            ON CAST(e.BundleSequence AS VARCHAR(50)) = CAST(b.Sequence AS VARCHAR(50))
        INNER JOIN Regions r
            ON CAST(r.TestEnvironment AS VARCHAR(50)) = CAST(b.TestEnvironment AS VARCHAR(50))
        INNER JOIN MiscEnvironmentSystem mes
            ON LEFT(LTRIM(RTRIM(r.Id)), 3) = LEFT(LTRIM(RTRIM(mes.Region)), 3)
        WHERE b.Id NOT LIKE '%Special%'
            AND ISNULL(b.TestEnvironment, 0) <> 0
            AND b.BundleProdImpDate >= ?
            AND b.BundleProdImpDate < ?
            AND mes.Region LIKE 'DV%'
            AND e.BundleExitDate IS NULL
        """

        assignments: list[RegionAssignment] = []
        with self.db_service.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                query,
                start_date,
                end_date,
            )
            for row in cursor.fetchall():
                assignments.append(
                    RegionAssignment(
                        bundle_id=str(getattr(row, "BundleId", "")).strip(),
                        bundle_sequence=str(
                            getattr(
                                row,
                                "BundleSequence",
                                "",
                            )
                        ).strip(),
                        bundle_test_environment=str(
                            getattr(
                                row,
                                "BundleTestEnvironment",
                                "",
                            )
                        ).strip(),
                        bundle_prod_imp_date=str(
                            getattr(
                                row,
                                "BundleProdImpDate",
                                "",
                            )
                        ).strip(),
                        region_id=str(getattr(row, "RegionId", "")).strip(),
                        region_prefix=str(getattr(row, "RegionPrefix", "")).strip(),
                        region=str(getattr(row, "Region", "")).strip(),
                        system=str(getattr(row, "System", "")).strip(),
                        effort_id=str(getattr(row, "EffortId", "")).strip(),
                    )
                )

        return assignments


class RegionInventoryAudit:
    def __init__(
        self,
        settings: dict[str, Any],
        base_dir: Path,
        inventory_file: Path | None = None,
        ndvr_source: Path | None = None,
        output_folder: Path | None = None,
        assignment_client: SqlRegionAssignmentClient | None = None,
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
        self.assignment_client = assignment_client or SqlRegionAssignmentClient(
            DBService(settings["database"])
        )

    def run(
        self,
        today: date | None = None,
    ) -> list[Path]:
        start_date, end_date = report_window(today or date.today())
        assignments = self.assignment_client.load_region_assignments(
            start_date=start_date,
            end_date=end_date,
        )
        rows = self._build_rows(assignments)
        output_folder = self.output_folder / "Region Inventory Audit"
        output_folder.mkdir(
            parents=True,
            exist_ok=True,
        )
        output_path = output_folder / "Region_Inventory_Audit.xlsx"
        export_xlsx(
            output_path=output_path,
            sheets={
                "Summary": (
                    SUMMARY_HEADERS,
                    self._summary_rows(
                        rows=rows,
                        assignments=assignments,
                    ),
                ),
                "SQL Assignments": (
                    ASSIGNMENT_HEADERS,
                    self._assignment_rows(assignments),
                ),
                "Detail": (
                    DETAIL_HEADERS,
                    [row.as_list() for row in rows] or self._empty_detail_rows(),
                ),
            },
        )
        return [output_path]

    def build_rows(
        self,
        today: date | None = None,
    ) -> list[RegionAuditRow]:
        start_date, end_date = report_window(today or date.today())
        assignments = self.assignment_client.load_region_assignments(
            start_date=start_date,
            end_date=end_date,
        )
        return self._build_rows(assignments)

    def _build_rows(
        self,
        assignments: list[RegionAssignment],
    ) -> list[RegionAuditRow]:
        groups = self._group_assignments(assignments)
        inventory_lookup = self._build_inventory_lookup()
        location_service = MainframeLocationService().load_file(
            latest_ndvr_file(self.ndvr_source, self.base_dir)
        )

        rows: list[RegionAuditRow] = []
        for group in groups:
            records = self._records_for_system(
                location_service=location_service,
                system=group.system,
            )
            for record in records:
                rows.append(
                    self._build_row(
                        group=group,
                        record=record,
                        inventory_references=inventory_lookup.get(record.key, []),
                    )
                )

        return sorted(
            rows,
            key=lambda row: (
                row.region.upper(),
                row.system.upper(),
                row.bundle_id.upper(),
                row.severity,
                row.element.upper(),
                row.type.upper(),
            ),
        )

    def _assignment_rows(
        self,
        assignments: list[RegionAssignment],
    ) -> list[list[object]]:
        rows = [
            [
                assignment.bundle_id,
                assignment.bundle_sequence,
                assignment.bundle_test_environment,
                assignment.bundle_prod_imp_date,
                assignment.region_id,
                assignment.region_prefix,
                assignment.region,
                assignment.system,
                assignment.effort_id,
            ]
            for assignment in sorted(
                assignments,
                key=lambda assignment: (
                    assignment.bundle_id.upper(),
                    assignment.region.upper(),
                    assignment.system.upper(),
                    assignment.effort_id.upper(),
                ),
            )
        ]

        return rows or [["", "", "", "", "", "", "", "", "No SQL assignments found."]]

    def _build_row(
        self,
        group: RegionAssignmentGroup,
        record: MainframeLocationRecord,
        inventory_references: list[InventoryReference],
    ) -> RegionAuditRow:
        inventory_efforts = tuple(
            sorted(
                {
                    reference.effort_id
                    for reference in inventory_references
                    if reference.effort_id
                }
            )
        )
        approved_efforts = self._approved_efforts(
            record=record,
            group=group,
            inventory_efforts=inventory_efforts,
        )

        if approved_efforts and not inventory_efforts:
            return self._row(
                group=group,
                record=record,
                inventory_efforts=inventory_efforts,
                approved_efforts=approved_efforts,
                status=STATUS_POTENTIAL_MISSING_INVENTORY,
                severity="WARNING",
                reason="Potential missing inventory but effort approved there.",
            )

        if not approved_efforts:
            return self._row(
                group=group,
                record=record,
                inventory_efforts=inventory_efforts,
                approved_efforts=approved_efforts,
                status=STATUS_IMPROPER_ACTIVITY,
                severity="ERROR",
                reason="Found items with efforts not approved for this region.",
            )

        return self._row(
            group=group,
            record=record,
            inventory_efforts=inventory_efforts,
            approved_efforts=approved_efforts,
            status=STATUS_APPROVED,
            severity="OK",
            reason="Element/type is tracked in inventory and approved for this region.",
        )

    def _row(
        self,
        group: RegionAssignmentGroup,
        record: MainframeLocationRecord,
        inventory_efforts: tuple[str, ...],
        approved_efforts: tuple[str, ...],
        status: str,
        severity: str,
        reason: str,
    ) -> RegionAuditRow:
        return RegionAuditRow(
            status=status,
            severity=severity,
            region=group.region,
            system=group.system,
            bundle_id=group.bundle_id,
            element=record.element,
            type=record.type,
            ndvr_ccid=record.ccid,
            inventory_effort_ids=inventory_efforts,
            approved_effort_ids=approved_efforts,
            ndvr_env=record.env,
            ndvr_subsystem=record.subsystem,
            ndvr_version=record.version,
            ndvr_date=record.date_generated,
            ndvr_time=record.time_generated,
            reason=reason,
        )

    def _approved_efforts(
        self,
        record: MainframeLocationRecord,
        group: RegionAssignmentGroup,
        inventory_efforts: tuple[str, ...],
    ) -> tuple[str, ...]:
        approved_by_ccid = {
            effort_id
            for effort_id in group.effort_ids
            if effort_matches_ccid(
                effort_id=effort_id,
                ccid=record.ccid,
            )
        }
        approved_by_inventory = {
            effort_id
            for effort_id in inventory_efforts
            if effort_id.upper() in {item.upper() for item in group.effort_ids}
        }

        return tuple(sorted(approved_by_ccid | approved_by_inventory))

    def _group_assignments(
        self,
        assignments: list[RegionAssignment],
    ) -> list[RegionAssignmentGroup]:
        grouped: dict[tuple[str, str, str], set[str]] = defaultdict(set)

        for assignment in assignments:
            if not assignment.bundle_id or not assignment.region or not assignment.system:
                continue

            grouped[
                (
                    assignment.bundle_id,
                    assignment.region,
                    assignment.system,
                )
            ].add(assignment.effort_id)

        return [
            RegionAssignmentGroup(
                bundle_id=bundle_id,
                region=region,
                system=system,
                effort_ids=tuple(sorted(effort_id for effort_id in effort_ids if effort_id)),
            )
            for (bundle_id, region, system), effort_ids in grouped.items()
        ]

    def _records_for_system(
        self,
        location_service: MainframeLocationService,
        system: str,
    ) -> list[MainframeLocationRecord]:
        wanted_system = str(system).strip().upper()
        records_by_key: dict[tuple[str, str, str, str], MainframeLocationRecord] = {}

        for record in location_service.records:
            if record.system.strip().upper() != wanted_system:
                continue

            records_by_key.setdefault(
                (
                    record.element.upper(),
                    record.type.upper(),
                    record.env.upper(),
                    record.subsystem.upper(),
                ),
                record,
            )

        return list(records_by_key.values())

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
            element = str(row.get("Element", "")).strip()
            type_ = str(row.get("Type", "")).strip()
            effort_id = str(row.get("Project", "")).strip()
            if not element or not type_:
                continue

            lookup[
                (
                    element.upper(),
                    type_.upper(),
                )
            ].append(
                InventoryReference(
                    release=str(row.get("Release", "")).strip(),
                    effort_id=effort_id,
                    element=element,
                    type=type_,
                )
            )

        return dict(lookup)

    def _summary_rows(
        self,
        rows: list[RegionAuditRow],
        assignments: list[RegionAssignment] | None = None,
    ) -> list[list[object]]:
        grouped: dict[tuple[str, str], list[RegionAuditRow]] = defaultdict(list)
        for group in self._group_assignments(assignments or []):
            grouped[
                (
                    group.region_system,
                    group.bundle_id,
                )
            ] = []

        for row in rows:
            grouped[
                (
                    f"{row.region}/{row.system}",
                    row.bundle_id,
                )
            ].append(row)

        if not grouped:
            return [["", "", 0, 0, 0]]

        summary_rows: list[list[object]] = []
        for (region_system, bundle_id), group_rows in sorted(
            grouped.items(),
            key=lambda item: (
                item[0][1].upper(),
                item[0][0].upper(),
            ),
        ):
            summary_rows.append(
                [
                    region_system,
                    bundle_id,
                    sum(1 for row in group_rows if row.status == STATUS_APPROVED),
                    sum(
                        1
                        for row in group_rows
                        if row.status == STATUS_POTENTIAL_MISSING_INVENTORY
                    ),
                    sum(
                        1
                        for row in group_rows
                        if row.status == STATUS_IMPROPER_ACTIVITY
                    ),
                ]
            )

        return summary_rows

    def _empty_detail_rows(
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
                "",
                "No matching region/system NDVR records found.",
            ]
        ]


def effort_matches_ccid(
    effort_id: str,
    ccid: str,
) -> bool:
    clean_effort = str(effort_id).strip().upper()
    clean_ccid = str(ccid).strip().upper()

    if not clean_effort or not clean_ccid:
        return False

    return clean_effort.startswith(clean_ccid) or clean_ccid.startswith(clean_effort)


def report_window(
    today: date,
) -> tuple[date, date]:
    start_month = add_months(
        date(
            today.year,
            today.month,
            1,
        ),
        -1,
    )
    end_month = add_months(
        date(
            today.year,
            today.month,
            1,
        ),
        4,
    )
    return start_month, end_month


def add_months(
    value: date,
    months: int,
) -> date:
    month_index = (value.year * 12) + (value.month - 1) + months
    year = month_index // 12
    month = (month_index % 12) + 1
    return date(
        year,
        month,
        1,
    )


def parse_args(
    argv: list[str] | None = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create an XLSX audit of DV region/system inventory activity."
    )
    parser.add_argument(
        "--settings",
        default=str(REPO_ROOT / "settings.json"),
        help="Path to settings.json. Defaults to the repository settings file.",
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


def main(
    argv: list[str] | None = None,
) -> int:
    args = parse_args(argv)
    settings_path = Path(args.settings).resolve()
    settings = SettingsLoader(settings_path).load()
    base_dir = settings_path.parent

    generated_files = RegionInventoryAudit(
        settings=settings,
        base_dir=base_dir,
        inventory_file=Path(args.inventory_file) if args.inventory_file else None,
        ndvr_source=Path(args.ndvr_source) if args.ndvr_source else None,
        output_folder=Path(args.output_folder) if args.output_folder else None,
    ).run()

    print("Generated:")
    for file_path in generated_files:
        print(f"- {file_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
