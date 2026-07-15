from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from app.core.models import ReleaseEffort
from app.services.after_action_service import AfterActionService
from app.services.element_service import ElementService
from app.services.mainframe_location_service import MainframeLocationService


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
                )
            ]

        return []


def make_location_line(
    ndvr_package: str,
) -> str:
    fields = [
        ("PGM001", 8),
        ("OCOB", 8),
        ("PRIVATE0", 8),
        ("SYS1", 4),
        ("QUAL1", 5),
        ("2026/07/14", 10),
        ("12:00:00:00", 11),
        ("01.01", 5),
        ("USER01", 8),
        ("CCID01", 7),
        ("COMMENTS", 40),
        ("00004", 5),
        ("", 1),
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
