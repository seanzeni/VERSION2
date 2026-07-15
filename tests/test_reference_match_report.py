from __future__ import annotations

from pathlib import Path

from app.core.models import Element
from app.reports.reference_match_report import ReferenceMatchReport
from app.services.reference_element_service import ReferenceElementService


def test_reference_report_only_includes_selected_visible_matches(
    tmp_path: Path,
) -> None:
    """Reference reports represent matching items in the active move."""
    reference_path = tmp_path / "ods.csv"
    reference_path.write_text("Element,Type\nPGM001,OCOB\n", encoding="utf-8")
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
        title="ODS Elements",
        file_stem="ODS_Elements",
        list_name="ods",
        reference_service=service,
    )._build_rows(elements, include_empty=False)

    assert rows == [
        ["2026/07 release", "ABC", "PGM001", "OCOB", "USER1"]
    ]


def test_hippa_listener_report_includes_listener_details(
    tmp_path: Path,
) -> None:
    """HIPPA listener reports include listener metadata from the reference CSV."""
    reference_path = tmp_path / "hippa.csv"
    reference_path.write_text(
        "Element,Type,Listener,Listener Transactions\nPGM001,OCOB,L1,T1\n",
        encoding="utf-8",
    )
    service = ReferenceElementService()
    service.load("hippa_listener", reference_path)

    rows = ReferenceMatchReport(
        title="HIPPA Listeners",
        file_stem="HIPPA_Listeners",
        list_name="hippa_listener",
        reference_service=service,
        include_listener_details=True,
    )._build_rows(
        [
            Element(
                release="2026/07 release",
                project="ABC",
                element="PGM001",
                type="OCOB",
                source_row={"Submitter": "USER1"},
            )
        ],
        include_empty=False,
    )

    assert rows == [
        ["2026/07 release", "ABC", "PGM001", "OCOB", "USER1", "L1", "T1"]
    ]
