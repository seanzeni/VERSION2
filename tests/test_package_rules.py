from __future__ import annotations

from app.core.package_rules import contains_any_marker
from app.core.package_rules import is_archive_package
from app.core.package_rules import is_do_not_move
from app.core.package_rules import is_marked_prod
from app.core.package_rules import is_marked_qual
from app.core.package_rules import normalize_marker_text


def test_normalize_marker_text_uppercases_and_strips() -> None:
    """Verifies marker normalization removes spacing and uppercases text."""
    assert normalize_marker_text("  prod  ") == "PROD"


def test_is_archive_package_detects_arch() -> None:
    """Verifies package text containing archive markers is detected."""
    assert is_archive_package("archive aps") is True
    assert is_archive_package("normal move") is False


def test_contains_any_marker() -> None:
    """Verifies marker matching works against a configured marker list."""
    assert contains_any_marker("already in prod", ["PROD"]) is True
    assert contains_any_marker("already in prod", ["QUAL"]) is False


def test_is_do_not_move() -> None:
    """Verifies do-not-move markers are detected from package text."""
    assert is_do_not_move("please DO NOT MOVE this", ["DO NOT MOVE"]) is True


def test_is_marked_prod() -> None:
    """Verifies already-in-PROD markers are detected from package text."""
    assert is_marked_prod("already prod", ["PROD"]) is True
    assert is_marked_prod("IN PROD", ["PROD"]) is True


def test_is_marked_qual() -> None:
    """Verifies already-in-QUAL markers are detected from package text."""
    assert is_marked_qual("already qual", ["QUAL"]) is True
