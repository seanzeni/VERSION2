from __future__ import annotations
from app.core.formatter import build_record


def base_row() -> dict[str, str]:
    return {
        "Element": "PGM001",
        "Type": "OCOB",
        "Project": "ABCD999",
        "DSN ID": "DSN12345",
        "Release": "REL1",
        "Subsys": "SUB1",
        "System": "SYSTEM99",
        "Act Rgn": "DV01",
        "Application": "APP TEST",
        "Package": "PKG",
    }


def test_build_record_uses_dsn_id_first_four_at_position_18() -> None:
    """Verifies build record uses dsn id first four at position 18."""
    print(build_record(base_row(), "PROD"))
    assert build_record(base_row(), "PROD")[18:22] == "DSN1"


def test_build_record_sets_normal_prod_move_source_to_qual() -> None:
    """Verifies normal PROD moves pull from QUAL1."""
    assert build_record(base_row(), "PROD")[60:65] == "QUAL1"


def test_build_record_sets_archive_prod_move_source_to_prod() -> None:
    """Verifies archive PROD moves pull from PROD1."""
    row = base_row()
    row["Package"] = "ARCHIVE"

    assert build_record(row, "PROD")[60:65] == "PROD1"


def test_build_record_sets_qual_env_from_dv_region() -> None:
    """Verifies build record sets QUAL env from dv region."""
    assert build_record(base_row(), "QUAL")[60:65] == "DEVL1"
