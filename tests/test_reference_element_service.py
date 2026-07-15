from __future__ import annotations

from pathlib import Path

import pytest

from app.services.reference_element_service import ReferenceElementService


def test_reference_workbook_matches_element_and_type_case_insensitively(
    tmp_path: Path,
) -> None:
    """Configured reference CSV files are normalized when loaded."""
    path = tmp_path / "hippa.csv"
    path.write_text("Element,Type,Listener\nPGM001,OCOB,LISTENER1\n", encoding="utf-8")

    service = ReferenceElementService()
    service.load("hippa_listener", path)

    assert service.matches("hippa_listener", "pgm001", "ocob")
    assert service.get("hippa_listener", "PGM001", "OCOB") == {
        "Element": "PGM001",
        "Type": "OCOB",
        "Listener": "LISTENER1",
    }
    assert not service.matches("hippa_listener", "PGM001", "OAPS")


def test_reference_workbook_requires_element_and_type_columns(
    tmp_path: Path,
) -> None:
    """A malformed reference CSV fails with a useful message."""
    path = tmp_path / "ods.csv"
    path.write_text("Program\nPGM001\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Element, Type"):
        ReferenceElementService().load("ods", path)
