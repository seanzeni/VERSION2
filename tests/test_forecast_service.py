from __future__ import annotations

from datetime import date

from app.core.models import ReleaseEffort
from app.services.forecast_service import ForecastService


class FakeDataLoader:
    def get_releases(self) -> list[str]:
        return [
            "2026/06 fep r2",
            "2026/07 release",
            "2026/08 release",
            "2026/09 release",
            "2026/10 release",
            "2026/06 special",
        ]

    def get_projects_for_release(self, release: str) -> set[str]:
        if release == "2026/06 special":
            return {"SPECIAL"}

        return {"SQL1", "INVONLY"}


class FakeDbService:
    def get_efforts_for_release(self, release: str) -> list[ReleaseEffort]:
        if release == "2026/06 special":
            return [
                ReleaseEffort(
                    effort_id="SPECIAL",
                    qual_date=date(2026, 6, 25),
                    prod_date=date(2026, 6, 30),
                )
            ]

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
    """Verifies forecast includes inventory not in SQL projects."""
    service = ForecastService(
        context=FakeContext(),
        report_registry=FakeReportRegistry(),
    )

    items = service.build_forecast_releases(today=date(2026, 6, 24))

    qual = next(item for item in items if item.mode == "QUAL")
    prod = next(item for item in items if item.mode == "PROD")
    assert qual.effort_ids == {"SQL1", "INVONLY"}
    assert prod.effort_ids == {"SQL1", "INVONLY"}


def test_forecast_includes_current_plus_next_three_non_special_months() -> None:
    """Verifies forecast includes current plus next three non special months."""
    service = ForecastService(
        context=FakeContext(),
        report_registry=FakeReportRegistry(),
    )

    items = service.build_forecast_releases(today=date(2026, 6, 24))
    releases = {item.release for item in items}

    assert "2026/06 fep r2" in releases
    assert "2026/07 release" in releases
    assert "2026/08 release" in releases
    assert "2026/09 release" in releases
    assert "2026/10 release" not in releases
    assert "2026/06 special" not in releases


def test_prod_forecast_bypasses_location_only_for_efforts_with_future_qual() -> None:
    """Verifies PROD forecast bypasses location only for efforts with future QUAL."""
    service = ForecastService(
        context=FakeContext(),
        report_registry=FakeReportRegistry(),
    )

    item = next(
        forecast
        for forecast in service.build_forecast_releases(today=date(2026, 6, 24))
        if forecast.release == "2026/06 fep r2" and forecast.mode == "PROD"
    )

    assert item.bypass_location_validation is False
    assert item.bypass_location_validation_effort_ids == {"SQL1"}


def test_forecast_thread_count_defaults_to_five() -> None:
    """Verifies forecast thread count defaults to five."""
    service = ForecastService(
        context=FakeContext(),
        report_registry=FakeReportRegistry(),
    )

    assert service.get_forecast_thread_count() == 5


def test_forecast_thread_count_uses_settings_value() -> None:
    """Verifies forecast thread count uses settings value."""
    class ContextWithForecastThreads(FakeContext):
        settings = {
            "reports": {
                "forecast_reports": {},
                "forecast_thread_count": 7,
            }
        }

    service = ForecastService(
        context=ContextWithForecastThreads(),
        report_registry=FakeReportRegistry(),
    )

    assert service.get_forecast_thread_count() == 7
