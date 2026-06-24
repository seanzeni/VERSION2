from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from app.core.app_state import AppState
from app.core.release_rules import ForecastRelease
from app.core.release_rules import all_prod_dates_before_today
from app.core.release_rules import forecast_months
from app.core.release_rules import has_future_or_today_date
from app.core.release_rules import is_regular_release_name
from app.core.release_rules import mode_date
from app.core.release_rules import month_key
from app.core.release_rules import parse_release_month
from app.reports.report_utils import archive_existing_reports
from app.reports.report_utils import safe_release_name


@dataclass(frozen=True, slots=True)
class ForecastResult:
    release: str
    mode: str
    output_folder: Path
    generated_files: list[Path]


class ForecastService:
    def __init__(
        self,
        context: Any,
        report_registry,
    ) -> None:
        self.context = context
        self.report_registry = report_registry

    def get_enabled_report_names(
        self,
    ) -> list[str]:
        configured = dict(
            self.context.settings.get(
                "reports",
                {},
            ).get(
                "forecast_reports",
                {},
            )
        )

        return [
            report_name
            for report_name in self.report_registry.get_names()
            if bool(configured.get(report_name, False))
        ]

    def build_forecast_releases(
        self,
        today: date,
    ) -> list[ForecastRelease]:
        releases = self.context.data_loader.get_releases()
        include_current_month = True

        current_regular_releases = [
            release
            for release in releases
            if is_regular_release_name(release)
            and parse_release_month(release) == (today.year, today.month)
        ]

        for release in current_regular_releases:
            efforts = self.context.db_service.get_efforts_for_release(release)
            if all_prod_dates_before_today(efforts, today):
                include_current_month = False
                break

        wanted_months = forecast_months(
            today=today,
            include_current_month=include_current_month,
        )

        forecast_items: list[ForecastRelease] = []

        for release in releases:
            release_month = parse_release_month(release)
            if release_month is None:
                continue

            if release_month not in wanted_months:
                continue

            if not is_regular_release_name(release):
                continue

            efforts = self.context.db_service.get_efforts_for_release(release)
            sql_effort_ids = {
                effort.effort_id.strip()
                for effort in efforts
                if effort.effort_id.strip()
            }
            inventory_effort_ids = self.context.data_loader.get_projects_for_release(
                release,
            )
            inventory_not_in_sql_ids = inventory_effort_ids - sql_effort_ids

            qual_ids = {
                effort.effort_id.strip()
                for effort in efforts
                if effort.effort_id.strip()
                and (mode_date(effort, "QUAL") is not None)
                and mode_date(effort, "QUAL") >= today
            }

            if qual_ids or inventory_not_in_sql_ids:
                forecast_items.append(
                    ForecastRelease(
                        release=release,
                        month_key=month_key(*release_month),
                        mode="QUAL",
                        bypass_location_validation=False,
                        effort_ids=qual_ids | inventory_not_in_sql_ids,
                    )
                )

            prod_ids = {
                effort.effort_id.strip()
                for effort in efforts
                if effort.effort_id.strip()
                and (mode_date(effort, "PROD") is not None)
                and mode_date(effort, "PROD") >= today
            }

            if prod_ids or inventory_not_in_sql_ids:
                forecast_items.append(
                    ForecastRelease(
                        release=release,
                        month_key=month_key(*release_month),
                        mode="PROD",
                        bypass_location_validation=has_future_or_today_date(
                            efforts=efforts,
                            mode="QUAL",
                            today=today,
                        ),
                        effort_ids=prod_ids | inventory_not_in_sql_ids,
                    )
                )

        return forecast_items

    def generate_forecast(
        self,
        base_output_folder: Path,
        formats: list[str],
        include_empty: bool,
        today: date | None = None,
    ) -> list[ForecastResult]:
        today = today or date.today()
        report_names = self.get_enabled_report_names()
        results: list[ForecastResult] = []

        for forecast_release in self.build_forecast_releases(today):
            state = self._build_state(
                forecast_release=forecast_release,
            )

            output_folder = (
                Path(base_output_folder)
                / "3 Month Forecast"
                / forecast_release.month_key
                / forecast_release.mode
                / safe_release_name(forecast_release.release)
            )
            output_folder.mkdir(
                parents=True,
                exist_ok=True,
            )
            archive_existing_reports(output_folder)

            generated_files: list[Path] = []
            for report_name in report_names:
                for output_format in formats:
                    try:
                        output_path = self.report_registry.generate(
                            name=report_name,
                            output_format=output_format,
                            state=state,
                            output_folder=output_folder,
                            include_empty=include_empty,
                        )
                    except NotImplementedError:
                        continue

                    if output_path is not None:
                        generated_files.append(output_path)

            results.append(
                ForecastResult(
                    release=forecast_release.release,
                    mode=forecast_release.mode,
                    output_folder=output_folder,
                    generated_files=generated_files,
                )
            )

        return results

    def _build_state(
        self,
        forecast_release: ForecastRelease,
    ) -> AppState:
        release = forecast_release.release
        mode = forecast_release.mode
        release_efforts = self.context.db_service.get_efforts_for_release(release)

        release_df = self.context.data_loader.filter_release_projects(
            release=release,
            projects=forecast_release.effort_ids,
        )
        selected_elements = self.context.element_service.build_elements(release_df)
        all_release_elements = self.context.element_service.build_elements(
            self.context.data_loader.filter_release(release)
        )
        inventory_effort_ids = {
            element.project
            for element in all_release_elements
            if element.project
        }
        effort_release_lookup = self.context.db_service.build_effort_release_lookup(
            inventory_effort_ids,
        )

        validated_elements, inventory_issues = (
            self.context.validation_service.validate_elements(
                elements=selected_elements,
                all_release_elements=all_release_elements,
                release_efforts=release_efforts,
                effort_release_lookup=effort_release_lookup,
                location_service=self.context.location_service,
                mode=mode,
                release=release,
                skip_location_validation=forecast_release.bypass_location_validation,
            )
        )

        state = AppState(
            release=release,
            mode=mode,
            thread_count=self.context.state.thread_count,
            current_xls_path=self.context.state.current_xls_path,
            current_ndvr_path=self.context.state.current_ndvr_path,
            selected_effort_ids=set(forecast_release.effort_ids),
            inventory_effort_ids=inventory_effort_ids,
            release_efforts=release_efforts,
            loaded_elements=validated_elements,
            inventory_issues=inventory_issues,
            all_release_elements=all_release_elements,
            effort_release_lookup=effort_release_lookup,
        )
        state.effort_dates = {
            effort.effort_id.strip(): str(mode_date(effort, mode) or "Unknown")
            for effort in release_efforts
            if effort.effort_id.strip()
        }
        for effort_id in forecast_release.effort_ids:
            state.effort_dates.setdefault(
                effort_id,
                "Inventory Not In SQL",
            )
        return state
