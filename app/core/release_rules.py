from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from typing import Any

from app.core.models import ReleaseEffort


RELEASE_MONTH_PATTERN = re.compile(r"^\s*(\d{4})/(\d{2})\b")


@dataclass(frozen=True, slots=True)
class ForecastRelease:
    release: str
    month_key: str
    mode: str
    bypass_location_validation: bool
    bypass_location_validation_effort_ids: set[str]
    effort_ids: set[str]


@dataclass(frozen=True, slots=True)
class NextReleaseChoice:
    release: str
    mode: str
    effort_ids: set[str]


def parse_release_month(
    release: str,
) -> tuple[int, int] | None:
    match = RELEASE_MONTH_PATTERN.match(str(release))
    if match is None:
        return None

    year = int(match.group(1))
    month = int(match.group(2))

    if month < 1 or month > 12:
        return None

    return year, month


def month_key(
    year: int,
    month: int,
) -> str:
    return f"{year:04d}-{month:02d}"


def add_months(
    value: date,
    months: int,
) -> date:
    month_index = (value.year * 12 + value.month - 1) + months
    year = month_index // 12
    month = (month_index % 12) + 1
    return date(year, month, 1)


def forecast_months(
    today: date,
) -> set[tuple[int, int]]:
    first_month = date(today.year, today.month, 1)
    return {
        (
            add_months(first_month, offset).year,
            add_months(first_month, offset).month,
        )
        for offset in range(4)
    }


def is_regular_release_name(
    release: str,
) -> bool:
    clean_release = str(release).strip().lower()
    return (
        parse_release_month(clean_release) is not None
        and "release" in clean_release
        and "special" not in clean_release
    )


def is_forecast_release_name(
    release: str,
) -> bool:
    clean_release = str(release).strip().lower()
    return (
        parse_release_month(clean_release) is not None
        and "special" not in clean_release
    )


def coerce_date(
    value: Any,
) -> date | None:
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    text = str(value).strip()
    if not text:
        return None

    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue

    return None


def is_before_today(
    value: Any,
    today: date,
) -> bool:
    move_date = coerce_date(value)
    return move_date is not None and move_date < today


def mode_date(
    effort: ReleaseEffort,
    mode: str,
) -> date | None:
    if mode.upper() == "PROD":
        return coerce_date(effort.prod_date)

    return coerce_date(effort.qual_date)


def next_available_effort_ids(
    efforts: list[ReleaseEffort],
    mode: str,
    today: date,
) -> set[str]:
    dated_efforts = [
        (effort, mode_date(effort, mode))
        for effort in efforts
        if effort.effort_id.strip()
    ]
    future_dates = sorted(
        {
            effort_date
            for _effort, effort_date in dated_efforts
            if effort_date is not None and effort_date >= today
        }
    )

    if not future_dates:
        return set()

    next_date = future_dates[0]
    return {
        effort.effort_id.strip()
        for effort, effort_date in dated_efforts
        if effort_date == next_date
    }


def next_release_choice(
    releases: list[str],
    get_efforts_for_release,
    today: date,
) -> NextReleaseChoice | None:
    choices: list[tuple[date, tuple[int, int], int, str, str, set[str]]] = []

    for release in releases:
        release_month = parse_release_month(release)
        if release_month is None or not is_regular_release_name(release):
            continue

        efforts = get_efforts_for_release(release)

        for mode_priority, mode in enumerate(("QUAL", "PROD")):
            effort_ids = next_available_effort_ids(
                efforts=efforts,
                mode=mode,
                today=today,
            )

            if not effort_ids:
                continue

            move_dates = [
                mode_date(
                    effort=effort,
                    mode=mode,
                )
                for effort in efforts
                if effort.effort_id.strip() in effort_ids
            ]
            move_dates = [value for value in move_dates if value is not None]

            if not move_dates:
                continue

            choices.append(
                (
                    min(move_dates),
                    release_month,
                    mode_priority,
                    release,
                    mode,
                    effort_ids,
                )
            )

    if not choices:
        return None

    _move_date, _release_month, _mode_priority, release, mode, effort_ids = min(
        choices,
        key=lambda item: (
            item[0],
            item[1],
            item[2],
            item[3],
        ),
    )

    return NextReleaseChoice(
        release=release,
        mode=mode,
        effort_ids=effort_ids,
    )
