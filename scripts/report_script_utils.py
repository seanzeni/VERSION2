from __future__ import annotations

# Purpose:
#     Shared helpers for standalone report scripts.

from pathlib import Path


NDVR_PATTERNS = ("*.txt", "*.dat", "*.csv")


def resolve_path(
    value: str | Path,
    base_dir: Path,
) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return base_dir / path


def iter_ndvr_files(
    source: str | Path,
    base_dir: Path,
) -> list[Path]:
    source_path = resolve_path(source, base_dir)
    folder = source_path.parent if source_path.is_file() else source_path

    if not folder.exists():
        raise FileNotFoundError(f"NDVR source was not found: {folder}")

    if not folder.is_dir():
        raise NotADirectoryError(f"NDVR source is not a directory: {folder}")

    files = {
        file_path
        for pattern in NDVR_PATTERNS
        for file_path in folder.glob(pattern)
        if file_path.is_file()
    }

    return sorted(
        files,
        key=lambda file_path: (
            file_path.stat().st_mtime,
            file_path.name,
        ),
        reverse=True,
    )


def latest_ndvr_file(
    source: str | Path,
    base_dir: Path,
) -> Path:
    files = iter_ndvr_files(source, base_dir)
    if not files:
        raise FileNotFoundError(f"No NDVR files were found in: {source}")
    return files[0]
