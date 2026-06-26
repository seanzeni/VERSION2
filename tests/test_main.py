from __future__ import annotations

from pathlib import Path

import main


def test_get_app_dir_uses_executable_folder_when_frozen(monkeypatch) -> None:
    """Verifies PyInstaller builds load settings next to the executable."""
    executable = Path("C:/Tools/CoordinationModule/CoordinationModule.exe")

    monkeypatch.setattr(
        main.sys,
        "frozen",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        main.sys,
        "executable",
        str(executable),
    )

    assert main.get_app_dir() == executable.parent

