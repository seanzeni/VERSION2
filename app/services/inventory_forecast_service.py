from __future__ import annotations

# Purpose:
#     Find upcoming inventory-to-SQL problems across multiple releases.
#
# Used By:
#     ReportCenter
#
# Responsibilities:
#     - Include regular releases for the current month plus three months.
#     - Exclude Special releases.
#     - Include only SQL efforts with a pending QUAL or PROD move.
#     - Find missing, wrong-release, untracked, and unexpected inventory.

from collections import Counter
from datetime import date
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.models import ReleaseEffort
from app.core.release_rules import coerce_date
from app.core.release_rules import forecast_months
from app.core.release_rules import parse_release_month
from app.reports.inventory_forecast_report import InventoryForecastReport


class InventoryForecastService:
    def __init__(
        self,
        context: Any,
    ) -> None:
        self.context = context

    def get_releases(
        self,
        today: date,
    ) -> list[str]:
        regular_months = forecast_months(today)
        releases: list[str] = []
        for release in self.context.data_loader.get_releases():
            release_month = parse_release_month(release)
            if release_month is None:
                continue

            if "special" in str(release).lower():
                continue

            if release_month in regular_months:
                releases.append(release)

        return sorted(
            releases,
            key=lambda release: (
                parse_release_month(release) or (9999, 12),
                str(release).upper(),
            ),
        )

    def build_rows(
        self,
        today: date | None = None,
    ) -> list[list[object]]:
        today = today or date.today()
        generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        releases = self.get_releases(today)

        raw_inventory_lookup = self.context.data_loader.get_inventory_release_lookup()
        inventory_lookup = {
            str(project).strip().upper(): {
                str(release).strip()
                for release in project_releases
                if str(release).strip()
            }
            for project, project_releases in raw_inventory_lookup.items()
            if str(project).strip()
        }
        sql_release_lookup = {
            str(project).strip().upper(): str(release).strip()
            for project, release in self.context.db_service.build_effort_release_lookup(
                set(inventory_lookup.keys())
            ).items()
            if str(project).strip() and str(release).strip()
        }

        efforts_by_release: dict[str, dict[str, ReleaseEffort]] = {}
        counts_by_release: dict[str, Counter[str]] = {}
        for release in releases:
            efforts_by_release[release] = {
                effort.effort_id.strip().upper(): effort
                for effort in self.context.db_service.get_efforts_for_release(release)
                if effort.effort_id.strip()
            }
            counts_by_release[release] = self._get_project_counts(release)

        inventory_release_names = {
            inventory_release
            for inventory_releases in inventory_lookup.values()
            for inventory_release in inventory_releases
        }
        for inventory_release in inventory_release_names:
            if inventory_release not in counts_by_release:
                counts_by_release[inventory_release] = self._get_project_counts(
                    inventory_release
                )

        rows: list[list[object]] = []
        seen: set[tuple[str, str, str, str]] = set()

        for release in releases:
            inventory_counts = counts_by_release[release]
            efforts = efforts_by_release[release]

            for project, effort in sorted(efforts.items()):
                if effort.withdrawn:
                    continue

                next_move = self._next_move(effort, today)
                if next_move is None:
                    continue

                move_mode, move_date = next_move
                inventory_releases = inventory_lookup.get(project, set())
                inventory_release_keys = {
                    value.upper()
                    for value in inventory_releases
                }
                other_inventory_releases = {
                    value
                    for value in inventory_releases
                    if value.upper() != release.upper()
                }

                if effort.no_inventory:
                    unexpected_count = sum(
                        counts_by_release.get(value, Counter()).get(project, 0)
                        for value in inventory_releases
                    )
                    if unexpected_count:
                        self._append_row(
                            rows=rows,
                            seen=seen,
                            generated_at=generated_at,
                            release=release,
                            move_mode=move_mode,
                            move_date=move_date,
                            project=project,
                            status="Unexpected Inventory",
                            element_count=unexpected_count,
                            reason=(
                                "SQL marks this project as no inventory, "
                                "but inventory rows were found."
                            ),
                            expected_release=release,
                            inventory_release=", ".join(sorted(inventory_releases)),
                        )
                    continue

                if release.upper() in inventory_release_keys:
                    if other_inventory_releases:
                        self._append_row(
                            rows=rows,
                            seen=seen,
                            generated_at=generated_at,
                            release=release,
                            move_mode=move_mode,
                            move_date=move_date,
                            project=project,
                            status="Wrong Release",
                            element_count=sum(
                                counts_by_release.get(value, Counter()).get(project, 0)
                                for value in other_inventory_releases
                            ),
                            reason=(
                                "Additional inventory exists under a different "
                                "release than SQL expects."
                            ),
                            expected_release=release,
                            inventory_release=", ".join(
                                sorted(other_inventory_releases)
                            ),
                        )
                    continue

                if inventory_releases:
                    self._append_row(
                        rows=rows,
                        seen=seen,
                        generated_at=generated_at,
                        release=release,
                        move_mode=move_mode,
                        move_date=move_date,
                        project=project,
                        status="Wrong Release",
                        element_count=sum(
                            counts_by_release.get(value, Counter()).get(project, 0)
                            for value in inventory_releases
                        ),
                        reason=(
                            "Inventory exists, but it is assigned to a different "
                            "release than SQL expects."
                        ),
                        expected_release=release,
                        inventory_release=", ".join(sorted(inventory_releases)),
                    )
                else:
                    self._append_row(
                        rows=rows,
                        seen=seen,
                        generated_at=generated_at,
                        release=release,
                        move_mode=move_mode,
                        move_date=move_date,
                        project=project,
                        status="Missing Inventory",
                        element_count=0,
                        reason=(
                            "SQL expects inventory for this upcoming move, "
                            "but no inventory rows were found."
                        ),
                        expected_release=release,
                        inventory_release="",
                    )

            for project, element_count in sorted(inventory_counts.items()):
                sql_release = sql_release_lookup.get(project)
                if not sql_release:
                    self._append_row(
                        rows=rows,
                        seen=seen,
                        generated_at=generated_at,
                        release=release,
                        move_mode="Unknown",
                        move_date=None,
                        project=project,
                        status="Untracked In SQL",
                        element_count=element_count,
                        reason=(
                            "Inventory rows exist, but this project is not "
                            "connected to a release in SQL."
                        ),
                        expected_release="",
                        inventory_release=release,
                    )

        return sorted(
            rows,
            key=lambda row: (
                str(row[1]).upper(),
                str(row[3]),
                str(row[4]).upper(),
                str(row[5]).upper(),
            ),
        )

    def generate(
        self,
        output_folder: Path,
        formats: list[str],
        today: date | None = None,
    ) -> list[Path]:
        rows = self.build_rows(today=today)
        report = InventoryForecastReport()
        return [
            report.generate(
                output_format=output_format,
                rows=rows,
                output_folder=output_folder,
            )
            for output_format in formats
        ]

    def _get_project_counts(
        self,
        release: str,
    ) -> Counter[str]:
        dataframe = self.context.data_loader.filter_release(release)
        return Counter(
            str(value).strip().upper()
            for value in dataframe["Project"]
            if str(value).strip()
        )

    @staticmethod
    def _next_move(
        effort: ReleaseEffort,
        today: date,
    ) -> tuple[str, date] | None:
        candidates = [
            ("QUAL", coerce_date(effort.qual_date)),
            ("PROD", coerce_date(effort.prod_date)),
        ]
        future_moves = [
            (mode, move_date)
            for mode, move_date in candidates
            if move_date is not None and move_date >= today
        ]
        if not future_moves:
            return None

        return min(
            future_moves,
            key=lambda item: (
                item[1],
                0 if item[0] == "QUAL" else 1,
            ),
        )

    @staticmethod
    def _append_row(
        rows: list[list[object]],
        seen: set[tuple[str, str, str, str]],
        generated_at: str,
        release: str,
        move_mode: str,
        move_date: date | None,
        project: str,
        status: str,
        element_count: int,
        reason: str,
        expected_release: str,
        inventory_release: str,
    ) -> None:
        key = (
            str(release).upper(),
            str(project).upper(),
            str(status).upper(),
            str(inventory_release).upper(),
        )
        if key in seen:
            return

        seen.add(key)
        rows.append(
            [
                generated_at,
                release,
                move_mode,
                move_date.isoformat() if move_date is not None else "Unknown",
                project,
                status,
                element_count,
                reason,
                expected_release,
                inventory_release,
            ]
        )
