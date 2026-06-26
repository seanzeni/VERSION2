from __future__ import annotations

from app.core.models import ArchiveStatus
from app.core.models import Element
from app.core.models import FixStatus
from app.core.models import MovementStatus
from app.core.models import ScheduleStatus
from app.core.models import Severity


def test_element_key_is_uppercase_element_type() -> None:
    """Verifies element keys normalize element and type values."""
    element = Element(
        release="rel",
        project="abc",
        element="pgm001",
        type="ocob",
    )

    assert element.key == ("PGM001", "OCOB")


def test_do_not_move_is_info_hidden() -> None:
    """Verifies do-not-move status is informational but hidden."""
    element = Element(
        release="REL",
        project="ABC",
        element="PGM001",
        type="OCOB",
        movement_status=MovementStatus.DO_NOT_MOVE,
    )

    assert element.severity == Severity.INFO
    assert element.color == "hidden"


def test_missing_archive_is_error() -> None:
    """Verifies missing archive status is an error."""
    element = Element(
        release="REL",
        project="ABC",
        element="PGM001",
        type="OCOB",
        archive_status=ArchiveStatus.POTENTIAL_MISSING_ARCHIVE,
    )

    assert element.severity == Severity.ERROR
    assert element.color == "error"


def test_missing_program_move_is_warning() -> None:
    """Verifies missing program move status is a warning."""
    element = Element(
        release="REL",
        project="ABC",
        element="PGM001",
        type="OAPS",
        archive_status=ArchiveStatus.POTENTIAL_MISSING_PROGRAM_MOVE,
    )

    assert element.severity == Severity.WARNING
    assert element.color == "warning"


def test_exists_in_fixp1_is_warning() -> None:
    """Verifies FIXP1 matches are warning-level statuses."""
    element = Element(
        release="REL",
        project="ABC",
        element="PGM001",
        type="OCOB",
        fix_status=FixStatus.EXISTS_IN_FIXP1,
    )

    assert element.severity == Severity.WARNING
    assert element.color == "warning"


def test_statuses_are_self_documenting() -> None:
    """Verifies status enums provide report glossary descriptions."""
    assert ScheduleStatus.INVENTORY_NOT_IN_RELEASE.description
    assert ArchiveStatus.POTENTIAL_MISSING_ARCHIVE.description


def test_display_sort_key_errors_before_warnings_before_info() -> None:
    """Verifies display sort order puts errors before warnings and info."""
    error_element = Element(
        release="REL",
        project="ABC",
        element="BPGM",
        type="OCOB",
        archive_status=ArchiveStatus.POTENTIAL_MISSING_ARCHIVE,
    )
    warning_element = Element(
        release="REL",
        project="ABC",
        element="APGM",
        type="OAPS",
        archive_status=ArchiveStatus.POTENTIAL_MISSING_PROGRAM_MOVE,
    )
    info_element = Element(
        release="REL",
        project="ABC",
        element="CPGM",
        type="OCOB",
    )

    sorted_elements = sorted(
        [info_element, warning_element, error_element],
        key=lambda item: item.display_sort_key,
    )

    assert sorted_elements == [error_element, warning_element, info_element]
