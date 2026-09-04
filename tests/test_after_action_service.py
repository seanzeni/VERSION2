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


class StaticDbService:
    def __init__(
        self,
        efforts: list[ReleaseEffort],
    ) -> None:
        self.efforts = efforts

    def get_efforts_for_release(
        self,
        release: str,
    ) -> list[ReleaseEffort]:
        if release == "2026/07 release":
            return self.efforts

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
    assert output_files[0].name == "Effort_Move_Status_14_JUL_2026.csv"
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


def make_context_for_date(
    dataframe: pd.DataFrame,
    location_path: Path,
    qual_date: date,
    prod_date: date,
) -> SimpleNamespace:
    context = make_context(dataframe, location_path)
    context.db_service = StaticDbService(
        [
            ReleaseEffort(
                effort_id="ABC",
                qual_date=qual_date,
                prod_date=prod_date,
            )
        ]
    )
    return context


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

    assert rows[0][14] == "Archived Requested - confirmed no longer in Prod"


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

    assert rows[0][12] == "2026-07-15"
    assert rows[0][14] == "OK"


def test_after_action_move_before_selected_date_reports_moved_early(
    tmp_path: Path,
) -> None:
    """Expected-location moves before the selected date report as moved early."""
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
    assert rows[0][9] == "No"
    assert rows[0][10] == "ABC"
    assert rows[0][12] == "2026-07-12"
    assert rows[0][13] == "10:00:00:00"
    assert rows[0][14] == (
        "Moved early. Expected move date was 2026-07-15, but the expected "
        "location was found on 2026-07-12 using package ABC."
    )


def test_after_action_unassociated_move_before_selected_date_reports_moved_early(
    tmp_path: Path,
) -> None:
    """Moved early reason takes precedence over package association detail."""
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

    assert rows[0][14] == (
        "Moved early. Expected move date was 2026-07-15, but the expected "
        "location was found on 2026-07-12 using package XYZ."
    )


def test_after_action_old_expected_env_move_reports_no_move_detected(
    tmp_path: Path,
) -> None:
    """Moves older than the early window use the normal last-move reason."""
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
            "ABC",
            env="PROD1",
            system="PRIVATE1",
            generated_date="2026/06/01",
        ),
        encoding="cp1252",
    )

    rows = AfterActionService(make_context(dataframe, location_path))._build_rows(
        selected_date=date(2026, 7, 15),
    )

    assert rows[0][10] == "ABC"
    assert rows[0][12] == "2026-06-01"
    assert rows[0][14] == (
        "No move detected for this date. Last move was 2026-06-01 using package "
        "ABC. Last package associated with Project ABC12345: Yes; currently "
        "associated with ABC12345."
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

    assert rows[0][14] == "Told us not to move."


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
    assert rows[0][12] == "2026-07-10"
    assert rows[0][14] == "Was moved outside of release."


def test_after_action_missing_qual_move_reports_higher_location(
    tmp_path: Path,
) -> None:
    """QUAL missing moves call out when the element already exists in PROD."""
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
            "PKG888",
            env="PROD1",
            system="PRIVATE1",
            generated_date="2026/07/13",
        ),
        encoding="cp1252",
    )

    rows = AfterActionService(make_context(dataframe, location_path))._build_rows(
        selected_date=date(2026, 7, 14),
    )

    assert rows[0][9] == "No"
    assert rows[0][10] == "PKG888"
    assert rows[0][12] == "2026-07-13"
    assert rows[0][14] == (
        "No move detected for this date. Found equal or higher NDVR location(s): "
        "PROD1 / PRIVATE1 / SYS1 on 2026-07-13 using package PKG888."
    )


def test_after_action_expected_env_prior_move_wins_over_higher_location(
    tmp_path: Path,
) -> None:
    """A prior QUAL1 move is reported as moved early before checking PROD1."""
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
        "\n".join(
            [
                make_location_line(
                    "QUALPKG",
                    env="QUAL1",
                    generated_date="2026/07/13",
                    time_generated="08:00:00:00",
                ),
                make_location_line(
                    "PRODPKG",
                    env="PROD1",
                    system="PRIVATE1",
                    generated_date="2026/07/13",
                    time_generated="09:00:00:00",
                ),
            ]
        ),
        encoding="cp1252",
    )

    rows = AfterActionService(make_context(dataframe, location_path))._build_rows(
        selected_date=date(2026, 7, 14),
    )

    assert rows[0][9] == "No"
    assert rows[0][10] == "QUALPKG"
    assert rows[0][12] == "2026-07-13"
    assert rows[0][14] == (
        "Moved early. Expected move date was 2026-07-14, but the expected "
        "location was found on 2026-07-13 using package QUALPKG."
    )


def test_after_action_ignores_future_higher_location_for_selected_date(
    tmp_path: Path,
) -> None:
    """Future PROD evidence does not affect an earlier QUAL after-action date."""
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
        "\n".join(
            [
                make_location_line(
                    "QUALPKG",
                    env="QUAL1",
                    generated_date="2026/07/13",
                ),
                make_location_line(
                    "PRODPKG",
                    env="PROD1",
                    system="PRIVATE1",
                    generated_date="2026/07/15",
                ),
            ]
        ),
        encoding="cp1252",
    )

    rows = AfterActionService(make_context(dataframe, location_path))._build_rows(
        selected_date=date(2026, 7, 14),
    )

    assert rows[0][10] == "QUALPKG"
    assert rows[0][12] == "2026-07-13"
    assert rows[0][14] == (
        "Moved early. Expected move date was 2026-07-14, but the expected "
        "location was found on 2026-07-13 using package QUALPKG."
    )


def test_after_action_uses_selected_date_ndvr_files_from_directory(
    tmp_path: Path,
) -> None:
    """Selected-date snapshots are loaded without sweeping older files."""
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
    ndvr_folder = tmp_path / "ndvr"
    ndvr_folder.mkdir()
    old_file = ndvr_folder / "NDVR-20260712.txt"
    qual_file = ndvr_folder / "NDVR-20260713.txt"
    prod_file = ndvr_folder / "NDVR-20260715.txt"
    old_file.write_text(
        make_location_line(
            "OLDPKG",
            env="QUAL1",
            generated_date="2026/07/12",
        ),
        encoding="cp1252",
    )
    qual_file.write_text(
        make_location_line(
            "QUALPKG",
            env="QUAL1",
            generated_date="2026/07/13",
        ),
        encoding="cp1252",
    )
    prod_file.write_text(
        make_location_line(
            "PRODPKG",
            env="PROD1",
            system="PRIVATE1",
            generated_date="2026/07/15",
        ),
        encoding="cp1252",
    )
    context = make_context_for_date(
        dataframe=dataframe,
        location_path=prod_file,
        qual_date=date(2026, 7, 13),
        prod_date=date(2026, 7, 15),
    )
    context.base_dir = tmp_path
    context.settings = {
        "files": {
            "default_ndvr_file": str(ndvr_folder),
        }
    }

    rows = AfterActionService(context)._build_rows(
        selected_date=date(2026, 7, 13),
    )

    assert rows[0][10] == "QUALPKG"
    assert rows[0][12] == "2026-07-13"
    assert rows[0][14] == "OK"


def test_after_action_uses_next_ndvr_file_date_when_selected_date_missing(
    tmp_path: Path,
) -> None:
    """Weekend gaps fall forward to the next available NDVR snapshot date."""
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
    ndvr_folder = tmp_path / "ndvr"
    ndvr_folder.mkdir()
    friday_file = ndvr_folder / "NDVR-20260710.txt"
    monday_file = ndvr_folder / "NDVR-20260713.txt"
    friday_file.write_text(
        make_location_line(
            "FRIPKG",
            env="QUAL1",
            generated_date="2026/07/10",
        ),
        encoding="cp1252",
    )
    monday_file.write_text(
        make_location_line(
            "MONPKG",
            env="QUAL1",
            generated_date="2026/07/12",
        ),
        encoding="cp1252",
    )
    context = make_context_for_date(
        dataframe=dataframe,
        location_path=friday_file,
        qual_date=date(2026, 7, 12),
        prod_date=date(2026, 7, 15),
    )
    context.base_dir = tmp_path
    context.settings = {
        "files": {
            "default_ndvr_file": str(ndvr_folder),
        }
    }

    rows = AfterActionService(context)._build_rows(
        selected_date=date(2026, 7, 12),
    )

    assert rows[0][10] == "MONPKG"
    assert rows[0][12] == "2026-07-12"
    assert rows[0][14] == "OK"


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
