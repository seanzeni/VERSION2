from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from app.core.app_state import AppState
from app.core.models import ReleaseEffort
from app.services.data_loader import DataLoader
from app.services.element_service import ElementService
from app.ui.main_window import MainWindow


REQUIRED_COLUMNS = [
    "Release",
    "Project",
    "Element",
    "Type",
    "Subsys",
    "System",
    "Act Rgn",
]


def write_inventory(
    tmp_path: Path,
) -> DataLoader:
    path = tmp_path / "inventory.xlsx"
    pd.DataFrame(
        [
            {
                "Release": "2026/08 release",
                "Project": "abc",
                "Element": "PGM001",
                "Type": "OCOB",
                "Subsys": "SYS1",
                "System": "PRIVATE0",
                "Act Rgn": "DV",
            }
        ]
    ).to_excel(path, index=False)
    data_loader = DataLoader(path, REQUIRED_COLUMNS)
    data_loader.load()
    return data_loader


def test_assignment_error_releases_show_inventory_assigned_to_wrong_release(
    tmp_path: Path,
) -> None:
    """Verifies assign_err expands to the inventory release name only."""
    window = MainWindow.__new__(MainWindow)
    window.app_state = AppState(
        release="2026/07 release",
        inventory_effort_ids=set(),
    )
    window.context = SimpleNamespace(
        data_loader=write_inventory(tmp_path),
        element_service=ElementService(),
    )

    releases = window._build_assignment_error_releases({"ABC"})

    assert releases == {"ABC": ["2026/08 release"]}


class FakeElementTable:
    def __init__(self) -> None:
        self.elements = []

    def load_elements(self, elements) -> None:
        self.elements = elements


class FakeStatsPanel:
    def update_statistics(self, statistics) -> None:
        return None


class FakeStatsService:
    def build_statistics(self, **kwargs) -> dict:
        return {}


class FakeValidationService:
    def __init__(self) -> None:
        self.received_effort_release_lookup = {}

    def validate_elements(
        self,
        elements,
        all_release_elements,
        release_efforts,
        effort_release_lookup,
        location_service,
        mode,
        release,
    ):
        self.received_effort_release_lookup = effort_release_lookup
        return elements, []


def test_assignment_error_elements_load_into_element_table(
    tmp_path: Path,
) -> None:
    """Verifies selected assignment-error efforts still load their elements."""
    validation_service = FakeValidationService()
    element_table = FakeElementTable()
    window = MainWindow.__new__(MainWindow)
    window.app_state = AppState(
        release="2026/07 release",
        mode="QUAL",
        selected_effort_ids={"ABC"},
        inventory_effort_ids=set(),
        release_efforts=[ReleaseEffort(effort_id="ABC")],
    )
    window.context = SimpleNamespace(
        data_loader=write_inventory(tmp_path),
        element_service=ElementService(),
        validation_service=validation_service,
        location_service=None,
        stats_service=FakeStatsService(),
    )
    window.element_table = element_table
    window.stats_panel = FakeStatsPanel()

    window.refresh_selected_elements()

    assert [element.element for element in element_table.elements] == ["PGM001"]
    assert validation_service.received_effort_release_lookup == {
        "ABC": "2026/07 release"
    }
