from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.core.models import Element
from app.reports.reference_match_report import ReferenceMatchReport
from app.services.reference_element_service import ReferenceElementService


def test_reference_report_only_includes_selected_visible_matches(
    tmp_path: Path,
) -> None:
    """Reference reports represent matching items in the active move."""
    reference_path = tmp_path / "ods.xlsx"
    pd.DataFrame(
        [{"Element": "PGM001", "Type": "OCOB"}]
    ).to_excel(reference_path, index=False)
    service = ReferenceElementService()
    service.load("ods", reference_path)

    elements = [
        Element(
            release="2026/07 release",
            project="ABC",
            element="PGM001",
            type="OCOB",
            source_row={"Submitter": "USER1"},
        ),
        Element(
            release="2026/07 release",
            project="ABC",
            element="PGM002",
            type="OCOB",
        ),
    ]
    rows = ReferenceMatchReport(
        title="ODS Report",
        file_stem="ODS_Report",
        list_name="ods",
        reference_service=service,
    )._build_rows(elements, include_empty=False)

    assert rows == [
        ["2026/07 release", "ABC", "PGM001", "OCOB", "USER1"]
    ]

