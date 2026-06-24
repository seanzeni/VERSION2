from __future__ import annotations

from datetime import date

from app.core.models import ReleaseEffort
from app.core.release_rules import forecast_months
from app.core.release_rules import is_forecast_release_name
from app.core.release_rules import is_regular_release_name
from app.core.release_rules import next_release_choice
from app.core.release_rules import next_available_effort_ids
from app.core.release_rules import parse_release_month


def test_regular_release_name_excludes_special() -> None:
    assert is_regular_release_name("2026/06 release") is True
    assert is_regular_release_name("2026/06 fep r2") is False
    assert is_regular_release_name("2026/06 special") is False
    assert is_regular_release_name("2026/06 (special name)") is False


def test_forecast_release_name_includes_non_special_month_names() -> None:
    assert is_forecast_release_name("2026/06 release") is True
    assert is_forecast_release_name("2026/06 fep r2") is True
    assert is_forecast_release_name("2026/06 special") is False


def test_parse_release_month() -> None:
    assert parse_release_month("2026/07 release") == (2026, 7)
    assert parse_release_month("release 2026/07") is None


def test_forecast_months_current_plus_next_three() -> None:
    assert forecast_months(date(2026, 12, 15)) == {
        (2026, 12),
        (2027, 1),
        (2027, 2),
        (2027, 3),
    }


def test_next_available_effort_ids_selects_all_on_next_mode_date() -> None:
    efforts = [
        ReleaseEffort(effort_id="B", prod_date=date(2026, 6, 25)),
        ReleaseEffort(effort_id="A", prod_date=date(2026, 6, 25)),
        ReleaseEffort(effort_id="C", prod_date=date(2026, 7, 1)),
    ]

    assert next_available_effort_ids(efforts, "PROD", date(2026, 6, 24)) == {
        "A",
        "B",
    }


def test_next_release_choice_uses_next_actual_mode_date() -> None:
    releases = ["2026/06 release", "2026/07 release"]
    effort_lookup = {
        "2026/06 release": [
            ReleaseEffort(
                effort_id="JUNE",
                qual_date=date(2026, 6, 20),
                prod_date=date(2026, 7, 10),
            )
        ],
        "2026/07 release": [
            ReleaseEffort(
                effort_id="JULYQUAL",
                qual_date=date(2026, 6, 26),
                prod_date=date(2026, 7, 15),
            )
        ],
    }

    choice = next_release_choice(
        releases=releases,
        get_efforts_for_release=lambda release: effort_lookup[release],
        today=date(2026, 6, 24),
    )

    assert choice is not None
    assert choice.release == "2026/07 release"
    assert choice.mode == "QUAL"
    assert choice.effort_ids == {"JULYQUAL"}
