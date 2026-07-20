from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from app.core.models import ReleaseEffort
from app.services.after_action_service import AfterActionService
from app.services.element_service import ElementService
from app.services.mainframe_location_service import MainframeLocationService
from app.services.status_marker_service import StatusMarkerService


class FakeDataLoader:
    def __init__(
        self,
        dataframe: pd.DataFrame,
    ) -> None:
        self.dataframe = dataframe

    def get_releases(
        self,
    ) -> list[str]:
        return sorted(self.dataframe["Release"].unique())

    def filter_release_projects(
        self,
        release: str,
        projects: set[str],
    ) -> pd.DataFrame:
        return self.dataframe[
            (self.dataframe["Release"] == release)
            & (self.dataframe["Project"].isin(projects))
        ].copy()


class FakeDbService:
    def get_efforts_for_release(
        self,
        release: str,
    ) -> list[ReleaseEffort]:
        if release == "2026/07 release":
            return [
                ReleaseEffort(
                    effort_id="ABC",
                    qual_date=date(2026, 7, 14),
                    prod_date=date(2026, 7, 15),
                ),
                ReleaseEffort(
                    effort_id="ABC12345",
                    qual_date=date(2026, 7, 14),
                    prod_date=date(2026, 7, 15),
                ),
                ReleaseEffort(
                    effort_id="FUTURE",
                    qual_date=date(2026, 7, 20),
                    prod_date=date(2026, 7, 21),
                ),
            ]

        return []


def make_location_line(
    ndvr_package: str,
    element: str = "PGM001",
    type_: str = "OCOB",
    env: str = "QUAL1",
    system: str = "PRIVATE0",
    generated_date: str = "2026/07/14",
    ndvr_rc: str = "00004",
    time_generated: str = "12:00:00:00",
) -> str:
    fields = [
        (element, 8),
        (type_, 8),
        (system, 8),
        ("SYS1", 4),
        (env, 5),
        (generated_date, 10),
        (time_generated, 11),
        ("01.01", 5),
        ("USER01", 8),
        ("CCID01", 7),
        ("COMMENTS", 40),
        (ndvr_rc, 5),
        (ndvr_package, 16),
    ]
    return " ".join(value.ljust(width)[:width] for value, width in fields)


def test_after_action_report_uses_ndvr_package_for_executed_date(
    tmp_path: Path,
) -> None:
    """Verifies after-action rows match executed QUAL bundles to NDVR packages."""
    dataframe = pd.DataFrame(
        [
            {
                "Release": "2026/07 release",
                "Project": "ABC",
                "Element": "PGM001",
                "Type": "OCOB",
                "System": "PRIVATE0",
                "Subsys": "SYS1",
            }
        ]
    )
    location_path = tmp_path / "locations.txt"
    location_path.write_text(
        make_location_line("PKG001"),
        encoding="cp1252",
    )
    context = SimpleNamespace(
        data_loader=FakeDataLoader(dataframe),
        db_service=FakeDbService(),
        element_service=ElementService(),
        location_service=MainframeLocationService().load_file(location_path),
    )

    output_files = AfterActionService(context).generate(
        selected_date=date(2026, 7, 14),
        output_folder=tmp_path / "after-action",
        formats=["csv"],
    )

    output_text = output_files[0].read_text(encoding="utf-8")
    assert "PKG001" in output_text
    assert "Yes" in output_text


def make_context(
    dataframe: pd.DataFrame,
    location_path: Path,
) -> SimpleNamespace:
    return SimpleNamespace(
        data_loader=FakeDataLoader(dataframe),
        db_service=FakeDbService(),
        element_service=ElementService(),
        location_service=MainframeLocationService().load_file(location_path),
        status_marker_service=StatusMarkerService(
            {
                "marker_columns": ["Package"],
                "do_not_move": ["DO NOT MOVE"],
                "already_in_prod": ["PROD"],
                "already_in_qual": ["QUAL"],
            }
        ),
    )


def test_after_action_archive_missing_from_prod_is_confirmed(
    tmp_path: Path,
) -> None:
    """Archive rows are confirmed by no longer being present in PROD1."""
    dataframe = pd.DataFrame(
        [
            {
                "Release": "2026/07 release",
                "Project": "ABC",
                "Element": "ARCH001",
                "Type": "OAPS",
                "System": "PRIVATE0",
                "Subsys": "SYS1",
                "Package": "ARCHIVE",
            }
        ]
    )
    location_path = tmp_path / "locations.txt"
    location_path.write_text(
        make_location_line("PKG001"),
        encoding="cp1252",
    )

    rows = AfterActionService(make_context(dataframe, location_path))._build_rows(
        selected_date=date(2026, 7, 15),
    )

    assert rows[0][13] == "Archived Requested - confirmed no longer in Prod"


def test_after_action_regular_rows_are_ok(
    tmp_path: Path,
) -> None:
    """Regular after-action rows use OK when no special marker applies."""
    dataframe = pd.DataFrame(
        [
            {
                "Release": "2026/07 release",
                "Project": "ABC",
                "Element": "PGM001",
                "Type": "OCOB",
                "System": "PRIVATE0",
                "Subsys": "SYS1",
                "Package": "",
            }
        ]
    )
    location_path = tmp_path / "locations.txt"
    location_path.write_text(
        make_location_line(
            "PKG001",
            env="PROD1",
            system="PRIVATE1",
            generated_date="2026/07/15",
        ),
        encoding="cp1252",
    )

    rows = AfterActionService(make_context(dataframe, location_path))._build_rows(
        selected_date=date(2026, 7, 15),
    )

    assert rows[0][13] == "OK"


def test_after_action_missing_move_reports_last_move_and_project_association(
    tmp_path: Path,
) -> None:
    """Missing moves show the last move date and inventory project association."""
    dataframe = pd.DataFrame(
        [
            {
                "Release": "2026/07 release",
                "Project": "ABC12345",
                "Element": "PGM001",
                "Type": "OCOB",
                "System": "PRIVATE0",
                "Subsys": "SYS1",
                "Package": "",
            }
        ]
    )
    location_path = tmp_path / "locations.txt"
    location_path.write_text(
        "\n".join(
            [
                make_location_line(
                    "ABC",
                    env="PROD1",
                    system="PRIVATE1",
                    generated_date="2026/07/12",
                    time_generated="10:00:00:00",
                ),
                make_location_line(
                    "XYZ",
                    env="PROD1",
                    system="PRIVATE1",
                    generated_date="2026/07/11",
                    time_generated="12:00:00:00",
                ),
            ]
        ),
        encoding="cp1252",
    )

    rows = AfterActionService(make_context(dataframe, location_path))._build_rows(
        selected_date=date(2026, 7, 15),
    )

    assert rows[0][3] == "ABC12345"
    assert rows[0][13] == (
        "No move detected for this date. Last move was 2026-07-12 using package "
        "ABC. Associated with inventory project ABC12345: Yes."
    )


def test_after_action_missing_move_reports_unassociated_last_move(
    tmp_path: Path,
) -> None:
    """Missing moves identify when the last move package does not match project."""
    dataframe = pd.DataFrame(
        [
            {
                "Release": "2026/07 release",
                "Project": "ABC12345",
                "Element": "PGM001",
                "Type": "OCOB",
                "System": "PRIVATE0",
                "Subsys": "SYS1",
                "Package": "",
            }
        ]
    )
    location_path = tmp_path / "locations.txt"
    location_path.write_text(
        make_location_line(
            "XYZ",
            env="PROD1",
            system="PRIVATE1",
            generated_date="2026/07/12",
        ),
        encoding="cp1252",
    )

    rows = AfterActionService(make_context(dataframe, location_path))._build_rows(
        selected_date=date(2026, 7, 15),
    )

    assert rows[0][13] == (
        "No move detected for this date. Last move was 2026-07-12 using package "
        "XYZ. Associated with inventory project ABC12345: No."
    )


def test_after_action_do_not_move_uses_marker_reason(
    tmp_path: Path,
) -> None:
    """Do-not-move rows show the requested marker reason."""
    dataframe = pd.DataFrame(
        [
            {
                "Release": "2026/07 release",
                "Project": "ABC",
                "Element": "PGM001",
                "Type": "OCOB",
                "System": "PRIVATE0",
                "Subsys": "SYS1",
                "Package": "DO NOT MOVE",
            }
        ]
    )
    location_path = tmp_path / "locations.txt"
    location_path.write_text(
        make_location_line("PKG001"),
        encoding="cp1252",
    )

    rows = AfterActionService(make_context(dataframe, location_path))._build_rows(
        selected_date=date(2026, 7, 14),
    )

    assert rows[0][13] == "Told us not to move."


def test_after_action_already_there_marker_reports_outside_release_move(
    tmp_path: Path,
) -> None:
    """Already-in-environment rows pull NDVR details and report outside release."""
    dataframe = pd.DataFrame(
        [
            {
                "Release": "2026/07 release",
                "Project": "ABC",
                "Element": "PGM001",
                "Type": "OCOB",
                "System": "PRIVATE0",
                "Subsys": "SYS1",
                "Package": "IN PROD",
            }
        ]
    )
    location_path = tmp_path / "locations.txt"
    location_path.write_text(
        make_location_line(
            "PKG999",
            env="PROD1",
            system="PRIVATE1",
            generated_date="2026/07/10",
            ndvr_rc="00012",
        ),
        encoding="cp1252",
    )

    rows = AfterActionService(make_context(dataframe, location_path))._build_rows(
        selected_date=date(2026, 7, 15),
    )

    assert rows[0][9] == "No"
    assert rows[0][10] == "PKG999"
    assert rows[0][11] == "00012"
    assert rows[0][13] == "Was moved outside of release."


def test_after_action_only_includes_inventory_scheduled_for_selected_date(
    tmp_path: Path,
) -> None:
    """Rows are limited to inventory projects scheduled for the selected move date."""
    dataframe = pd.DataFrame(
        [
            {
                "Release": "2026/07 release",
                "Project": "ABC",
                "Element": "TODAY01",
                "Type": "OCOB",
                "System": "PRIVATE0",
                "Subsys": "SYS1",
                "Package": "",
            },
            {
                "Release": "2026/07 release",
                "Project": "FUTURE",
                "Element": "LATER01",
                "Type": "OCOB",
                "System": "PRIVATE0",
                "Subsys": "SYS1",
                "Package": "",
            },
        ]
    )
    location_path = tmp_path / "locations.txt"
    location_path.write_text(
        make_location_line("PKG001"),
        encoding="cp1252",
    )

    rows = AfterActionService(make_context(dataframe, location_path))._build_rows(
        selected_date=date(2026, 7, 14),
    )

    assert [row[4] for row in rows] == ["TODAY01"]
