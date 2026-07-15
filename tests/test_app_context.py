from __future__ import annotations

# Purpose:
#     Verify AppContext startup file resolution safeguards.
#
# Annotations:
#     Uses postponed annotations to match application modules.
#
# Used By:
#     pytest
#
# Responsibilities:
#     - Confirm missing optional files can be selected at startup.
#     - Confirm remembered file settings are updated after selection.
#     - Confirm optional startup files can be skipped.
#     - Confirm required startup files still raise when not selected.
#
# Notes:
#     These tests exercise the file-resolution helper without constructing the
#     full desktop app context.

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.app_context import AppContext


def build_context(
    tmp_path: Path,
    default_ndvr_file: str = "missing-ndvr.txt",
) -> AppContext:
    settings = {
        "files": {
            "default_input_file": "missing-inventory.xlsx",
            "default_ndvr_file": default_ndvr_file,
            "remember_last_used_files": True,
        }
    }
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps(settings),
        encoding="utf-8",
    )

    context = AppContext.__new__(AppContext)
    context.base_dir = tmp_path
    context.settings_path = settings_path
    context.settings = settings

    return context


def test_missing_optional_startup_file_prompts_and_saves(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifies missing optional startup file prompts and saves."""
    selected_file = tmp_path / "ndvr.txt"
    selected_file.write_text(
        "content",
        encoding="utf-8",
    )
    context = build_context(tmp_path)

    monkeypatch.setattr(
        context,
        "prompt_for_file",
        lambda title, filetypes: selected_file,
    )

    resolved = context.resolve_startup_file(
        key="default_ndvr_file",
        title="Select NDVR/Mainframe Location File",
        filetypes=[("Text Files", "*.txt")],
        required=False,
    )

    saved_settings = json.loads(context.settings_path.read_text(encoding="utf-8"))

    assert resolved == selected_file
    assert saved_settings["files"]["default_ndvr_file"] == str(selected_file)


def test_missing_optional_startup_file_can_be_skipped(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifies missing optional startup file can be skipped."""
    context = build_context(tmp_path)

    monkeypatch.setattr(
        context,
        "prompt_for_file",
        lambda title, filetypes: None,
    )

    resolved = context.resolve_startup_file(
        key="default_ndvr_file",
        title="Select NDVR/Mainframe Location File",
        filetypes=[("Text Files", "*.txt")],
        required=False,
    )

    assert resolved is None


def test_missing_required_startup_file_raises_when_skipped(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifies missing required startup file raises when skipped."""
    context = build_context(tmp_path)

    monkeypatch.setattr(
        context,
        "prompt_for_file",
        lambda title, filetypes: None,
    )

    with pytest.raises(FileNotFoundError):
        context.resolve_startup_file(
            key="default_input_file",
            title="Select Inventory Spreadsheet",
            filetypes=[("Excel Files", "*.xlsx")],
            required=True,
            missing_message="No inventory spreadsheet was selected.",
        )


def make_ndvr_line(
    element: str,
) -> str:
    fields = [
        (element, 8),
        ("OCOB", 8),
        ("PRIVATE0", 8),
        ("SYS1", 4),
        ("QUAL1", 5),
        ("2026/07/14", 10),
        ("12:00:00:00", 11),
        ("01.01", 5),
        ("USER01", 8),
        ("CCID01", 7),
        ("COMMENTS", 40),
        ("00000", 5),
        ("", 1),
        ("PKG001", 16),
    ]
    return " ".join(value.ljust(width)[:width] for value, width in fields)


def test_ndvr_directory_loads_latest_file_and_preserves_setting(
    tmp_path: Path,
) -> None:
    """Verifies a configured NDVR directory loads the newest matching file."""
    ndvr_folder = tmp_path / "ndvr"
    ndvr_folder.mkdir()
    old_file = ndvr_folder / "ndvr-inv-20260714080000.txt"
    new_file = ndvr_folder / "ndvr-inv-20260714120000.txt"
    old_file.write_text(make_ndvr_line("OLDPGM"), encoding="cp1252")
    new_file.write_text(make_ndvr_line("NEWPGM"), encoding="cp1252")
    os.utime(old_file, (1_000, 1_000))
    os.utime(new_file, (2_000, 2_000))

    context = build_context(
        tmp_path,
        default_ndvr_file=str(ndvr_folder),
    )
    context.state = SimpleNamespace(current_ndvr_path=None)

    resolved = context.resolve_startup_file(
        key="default_ndvr_file",
        title="Select NDVR/Mainframe Location File",
        filetypes=[("Text Files", "*.txt")],
        required=False,
    )
    service = context.load_location_file(resolved)
    saved_settings = json.loads(context.settings_path.read_text(encoding="utf-8"))

    assert resolved == ndvr_folder
    assert context.state.current_ndvr_path == new_file
    assert service.records[0].element == "NEWPGM"
    assert saved_settings["files"]["default_ndvr_file"] == str(ndvr_folder)
