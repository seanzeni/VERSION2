from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from app.core.app_state import AppState
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


def test_assignment_error_details_show_inventory_assigned_to_wrong_release(
    tmp_path: Path,
) -> None:
    """Verifies missing SQL efforts become assign_err when inventory exists elsewhere."""
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

    window = MainWindow.__new__(MainWindow)
    window.app_state = AppState(
        release="2026/07 release",
        inventory_effort_ids=set(),
    )
    window.context = SimpleNamespace(
        data_loader=data_loader,
        element_service=ElementService(),
    )

    details = window._build_assignment_error_details({"ABC"})

    assert list(details) == ["ABC"]
    assert details["ABC"] == [
        (
            "PGM001 OCOB: Inventory identified bundle does not match the RSET "
            "bundle for this project. Inventory says project abc belongs to the "
            "release bundle [2026/08 release], but RSET states it belongs to "
            "this release [2026/07 release]."
        )
    ]
