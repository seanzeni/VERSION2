from __future__ import annotations

from datetime import date

from app.core.models import ReleaseEffort
from app.core.release_rules import forecast_months
from app.core.release_rules import is_regular_release_name
from app.core.release_rules import next_available_effort_ids
from app.core.release_rules import parse_release_month


def test_regular_release_name_excludes_special() -> None:
    assert is_regular_release_name("2026/06 release") is True
    assert is_regular_release_name("2026/06 special") is False
    assert is_regular_release_name("2026/06 (special name)") is False


def test_parse_release_month() -> None:
    assert parse_release_month("2026/07 release") == (2026, 7)
    assert parse_release_month("release 2026/07") is None


def test_forecast_months_current_plus_next_two() -> None:
    assert forecast_months(date(2026, 12, 15), True) == {
        (2026, 12),
        (2027, 1),
        (2027, 2),
    }


def test_forecast_months_next_three() -> None:
    assert forecast_months(date(2026, 12, 15), False) == {
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
