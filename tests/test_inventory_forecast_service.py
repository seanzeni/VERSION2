from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from app.core.models import ReleaseEffort
from app.reports.report_utils import make_writable
from app.services.inventory_forecast_service import InventoryForecastService


class FakeDataLoader:
    projects_by_release = {
        "2026/06 release": [
            "GOOD",
            "NOINV",
            "UNTRACK",
            "WITHDRAWN",
        ],
        "2026/07 special": ["WRONG", "GOOD"],
        "2026/08 special": ["SPECIAL2"],
        "2026/09 release": [],
        "2026/10 release": [],
    }

    def get_releases(self) -> list[str]:
        return list(self.projects_by_release.keys())

    def get_inventory_release_lookup(self) -> dict[str, set[str]]:
        lookup: dict[str, set[str]] = {}
        for release, projects in self.projects_by_release.items():
            for project in projects:
                lookup.setdefault(project, set()).add(release)
        return lookup

    def filter_release(self, release: str) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "Project": self.projects_by_release.get(release, []),
            }
        )


class FakeDbService:
    def get_efforts_for_release(self, release: str) -> list[ReleaseEffort]:
        if release != "2026/06 release":
            return []

        return [
            ReleaseEffort(
                effort_id="GOOD",
                qual_date=date(2026, 6, 20),
                prod_date=date(2026, 6, 27),
            ),
            ReleaseEffort(
                effort_id="MISS",
                qual_date=date(2026, 6, 21),
                prod_date=date(2026, 6, 28),
            ),
            ReleaseEffort(
                effort_id="WRONG",
                qual_date=date(2026, 6, 10),
                prod_date=date(2026, 6, 25),
            ),
            ReleaseEffort(
                effort_id="NOINV",
                qual_date=date(2026, 6, 22),
                no_inventory=True,
            ),
            ReleaseEffort(
                effort_id="PAST",
                qual_date=date(2026, 6, 1),
                prod_date=date(2026, 6, 10),
            ),
            ReleaseEffort(
                effort_id="WITHDRAWN",
                qual_date=date(2026, 6, 23),
                exit_date=date(2026, 6, 5),
            ),
        ]

    def build_effort_release_lookup(
        self,
        effort_ids: set[str],
    ) -> dict[str, str]:
        expected = {
            "GOOD": "2026/06 release",
            "NOINV": "2026/06 release",
            "WRONG": "2026/06 release",
            "WITHDRAWN": "2026/06 release",
        }
        return {
            effort_id: expected[effort_id]
            for effort_id in effort_ids
            if effort_id in expected
        }


class FakeContext:
    data_loader = FakeDataLoader()
    db_service = FakeDbService()


def make_service() -> InventoryForecastService:
    return InventoryForecastService(
        context=FakeContext(),
    )


def test_release_window_excludes_special_releases() -> None:
    """Inventory forecasting only includes standard releases."""
    releases = make_service().get_releases(
        today=date(2026, 6, 15),
    )

    assert "2026/06 release" in releases
    assert "2026/07 special" not in releases
    assert "2026/08 special" not in releases
    assert "2026/09 release" in releases
    assert "2026/10 release" not in releases


def test_inventory_forecast_finds_only_upcoming_inventory_problems() -> None:
    """Verifies consolidated output classifies future inventory problems."""
    rows = make_service().build_rows(
        today=date(2026, 6, 15),
    )
    by_status = {
        row[5]: row
        for row in rows
    }

    assert set(by_status) == {
        "Missing Inventory",
        "Wrong Release",
        "Unexpected Inventory",
        "Untracked In SQL",
    }
    assert by_status["Missing Inventory"][4] == "MISS"
    wrong_release_rows = [
        row
        for row in rows
        if row[5] == "Wrong Release"
    ]
    assert {row[4] for row in wrong_release_rows} == {"GOOD", "WRONG"}
    assert next(row for row in wrong_release_rows if row[4] == "WRONG")[2] == "PROD"
    assert by_status["Unexpected Inventory"][4] == "NOINV"
    assert by_status["Untracked In SQL"][4] == "UNTRACK"
    assert all(row[4] not in {"PAST", "WITHDRAWN"} for row in rows)


def test_inventory_forecast_generates_selected_formats(tmp_path: Path) -> None:
    """Verifies the consolidated report supports CSV, XLSX, and PDF output."""
    outputs = make_service().generate(
        output_folder=tmp_path,
        formats=["csv", "xlsx", "pdf"],
        today=date(2026, 6, 15),
    )

    assert {path.suffix for path in outputs} == {".csv", ".xlsx", ".pdf"}
    assert all(path.exists() for path in outputs)
    for output in outputs:
        make_writable(output)
