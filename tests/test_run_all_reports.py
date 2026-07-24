from __future__ import annotations

import importlib.util
import os
import stat
import sys
from pathlib import Path
from types import SimpleNamespace


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


def test_build_tasks_includes_global_resync() -> None:
    """Verifies the all-report runner includes global resync."""
    assert "Global Resync" in {task.name for task in runner_module.build_tasks()}


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


def test_main_output_override_archives_after_generation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Verifies flat output files remain available while reports are generated."""
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    output_root = tmp_path / "drop"
    output_root.mkdir()
    old_file = output_root / "old.xlsx"
    old_file.write_text("old", encoding="utf-8")
    events: list[tuple] = []
    original_archive = runner_module.archive_existing_xlsx
    original_publish = runner_module.publish_xlsx_files

    def fake_create_context(
        args,
        staging_root=None,
    ):
        return SimpleNamespace(staging_root=staging_root)

    def fake_run_all(
        context,
    ):
        events.append(
            (
                "run",
                old_file.exists(),
            )
        )
        generated = context.staging_root / "new.xlsx"
        generated.write_text("new", encoding="utf-8")
        return [generated], []

    def tracking_archive(
        target_output_root: Path,
    ) -> None:
        events.append(
            (
                "archive",
                old_file.exists(),
            )
        )
        original_archive(target_output_root)

    def tracking_publish(
        generated_files: list[Path],
        output_root: Path,
    ) -> list[Path]:
        events.append(
            (
                "publish",
                old_file.exists(),
                (output_root / "History" / "old.xlsx").exists(),
            )
        )
        return original_publish(
            generated_files,
            output_root,
        )

    monkeypatch.setattr(
        runner_module,
        "create_context",
        fake_create_context,
    )
    monkeypatch.setattr(
        runner_module,
        "run_all",
        fake_run_all,
    )
    monkeypatch.setattr(
        runner_module,
        "archive_existing_xlsx",
        tracking_archive,
    )
    monkeypatch.setattr(
        runner_module,
        "publish_xlsx_files",
        tracking_publish,
    )

    exit_code = runner_module.main(
        [
            "--settings",
            str(settings_path),
            "--output",
            str(output_root),
        ]
    )

    assert exit_code == 0
    assert events == [
        (
            "run",
            True,
        ),
        (
            "archive",
            True,
        ),
        (
            "publish",
            False,
            True,
        ),
    ]
