from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from app.services.reference_element_service import ReferenceElementService


def test_reference_workbook_matches_element_and_type_case_insensitively(
    tmp_path: Path,
) -> None:
    """Configured reference workbooks are normalized when loaded."""
    path = tmp_path / "hipaa.xlsx"
    pd.DataFrame(
        [{"Element": "PGM001", "Type": "OCOB"}]
    ).to_excel(path, index=False)

    service = ReferenceElementService()
    service.load("hipaa_listener", path)

    assert service.matches("hipaa_listener", "pgm001", "ocob")
    assert not service.matches("hipaa_listener", "PGM001", "OAPS")


def test_reference_workbook_requires_element_and_type_columns(
    tmp_path: Path,
) -> None:
    """A malformed reference workbook fails with a useful message."""
    path = tmp_path / "ods.xlsx"
    pd.DataFrame([{"Program": "PGM001"}]).to_excel(path, index=False)

    with pytest.raises(ValueError, match="Element, Type"):
        ReferenceElementService().load("ods", path)

