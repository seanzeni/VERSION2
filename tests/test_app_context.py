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
from pathlib import Path

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
