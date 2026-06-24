from __future__ import annotations

from datetime import date

from app.core.models import ReleaseEffort
from app.services.forecast_service import ForecastService


class FakeDataLoader:
    def get_releases(self) -> list[str]:
        return ["2026/06 release"]

    def get_projects_for_release(self, release: str) -> set[str]:
        return {"SQL1", "INVONLY"}


class FakeDbService:
    def get_efforts_for_release(self, release: str) -> list[ReleaseEffort]:
        return [
            ReleaseEffort(
                effort_id="SQL1",
                qual_date=date(2026, 6, 25),
                prod_date=date(2026, 6, 30),
            )
        ]


class FakeContext:
    settings = {"reports": {"forecast_reports": {}}}
    data_loader = FakeDataLoader()
    db_service = FakeDbService()


class FakeReportRegistry:
    def get_names(self) -> list[str]:
        return []


def test_forecast_includes_inventory_not_in_sql_projects() -> None:
    service = ForecastService(
        context=FakeContext(),
        report_registry=FakeReportRegistry(),
    )

    items = service.build_forecast_releases(today=date(2026, 6, 24))

    qual = next(item for item in items if item.mode == "QUAL")
    prod = next(item for item in items if item.mode == "PROD")
    assert qual.effort_ids == {"SQL1", "INVONLY"}
    assert prod.effort_ids == {"SQL1", "INVONLY"}
