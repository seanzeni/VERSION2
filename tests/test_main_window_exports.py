from __future__ import annotations

from pathlib import Path

from app.core.models import Element
from app.services.reference_element_service import ReferenceElementService
from app.ui.main_window import partition_ods_export_elements


def make_element(
    name: str,
    package: str = "",
) -> Element:
    return Element(
        release="REL1",
        project="EFFORT1",
        element=name,
        type="OCOB",
        source_row={"Package": package},
    )


def load_ods_reference(tmp_path: Path) -> ReferenceElementService:
    reference_path = tmp_path / "ods.csv"
    reference_path.write_text(
        "Element,Type\nODS1,OCOB\nODSARCH,OCOB\n",
        encoding="utf-8",
    )
    service = ReferenceElementService()
    service.load("ods", reference_path)
    return service


def test_prod_export_separates_ods_moves_but_keeps_archives(
    tmp_path: Path,
) -> None:
    """Verifies ODS archives remain in the normal PROD export."""
    normal = make_element("NORMAL")
    ods = make_element("ODS1")
    ods_archive = make_element("ODSARCH", "ARCHIVE")

    standard, ods_only = partition_ods_export_elements(
        [normal, ods, ods_archive],
        "PROD",
        load_ods_reference(tmp_path),
    )

    assert standard == [normal, ods_archive]
    assert ods_only == [ods]


def test_qual_export_does_not_separate_ods_elements(tmp_path: Path) -> None:
    """Verifies ODS separation is limited to PROD exports."""
    normal = make_element("NORMAL")
    ods = make_element("ODS1")
    elements = [normal, ods]

    standard, ods_only = partition_ods_export_elements(
        elements,
        "QUAL",
        load_ods_reference(tmp_path),
    )

    assert standard == elements
    assert ods_only == []
