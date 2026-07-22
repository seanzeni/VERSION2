from __future__ import annotations

import importlib.util
import os
import stat
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_all_reports.py"
SPEC = importlib.util.spec_from_file_location("run_all_reports", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
runner_module = importlib.util.module_from_spec(SPEC)
sys.modules["run_all_reports"] = runner_module
SPEC.loader.exec_module(runner_module)


def test_archive_existing_xlsx_moves_files_to_history(
    tmp_path: Path,
) -> None:
    """Verifies output override archives old XLSX files before publishing."""
    output_root = tmp_path / "drop"
    output_root.mkdir()
    old_file = output_root / "old.xlsx"
    old_file.write_text(
        "old",
        encoding="utf-8",
    )
    ignored_file = output_root / "notes.pdf"
    ignored_file.write_text(
        "pdf",
        encoding="utf-8",
    )

    runner_module.archive_existing_xlsx(output_root)

    assert not old_file.exists()
    assert (output_root / "History" / "old.xlsx").exists()
    assert ignored_file.exists()


def test_publish_xlsx_files_copies_only_xlsx_and_marks_read_only(
    tmp_path: Path,
) -> None:
    """Verifies output override publishes only generated XLSX files."""
    staging = tmp_path / "staging"
    output_root = tmp_path / "drop"
    staging.mkdir()
    output_root.mkdir()
    xlsx_file = staging / "report.xlsx"
    pdf_file = staging / "report.pdf"
    xlsx_file.write_text(
        "xlsx",
        encoding="utf-8",
    )
    pdf_file.write_text(
        "pdf",
        encoding="utf-8",
    )

    published_files = runner_module.publish_xlsx_files(
        generated_files=[
            xlsx_file,
            pdf_file,
        ],
        output_root=output_root,
    )

    assert published_files == [output_root / "report.xlsx"]
    assert published_files[0].read_text(encoding="utf-8") == "xlsx"
    assert not (output_root / "report.pdf").exists()
    assert not os.stat(published_files[0]).st_mode & stat.S_IWRITE
