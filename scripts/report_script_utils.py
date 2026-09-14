from __future__ import annotations

# Purpose:
#     Shared helpers for standalone report scripts.

from pathlib import Path
from typing import Any
from urllib.parse import quote

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


def create_configured_email_drafts(
    settings: dict[str, Any],
    generated_files: list[Path],
    base_dir: Path,
) -> list[str]:
    email_settings = settings.get("email", {})
    if not email_settings.get("enabled", False):
        return []

    created: list[str] = []
    for report_name, report_settings in email_settings.get("reports", {}).items():
        if not isinstance(report_settings, dict):
            continue
        if not report_settings.get("enabled", False):
            continue

        matching_files = _matching_report_files(
            generated_files=generated_files,
            file_prefixes=report_settings.get("file_prefixes", []),
        )
        if not matching_files:
            continue

        if create_outlook_draft(
            email_settings=email_settings,
            report_settings=report_settings,
            report_name=report_name,
            generated_files=matching_files,
            base_dir=base_dir,
        ):
            created.append(report_name)

    return created


def create_outlook_draft(
    email_settings: dict[str, Any],
    report_settings: dict[str, Any],
    report_name: str,
    generated_files: list[Path],
    base_dir: Path,
) -> bool:
    try:
        import win32com.client  # type: ignore[import-not-found]
    except ImportError:
        print("Outlook draft skipped: pywin32 is not installed.")
        return False

    try:
        outlook = win32com.client.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)
        mail.To = _join_recipients(report_settings.get("to", []))
        mail.CC = _join_recipients(report_settings.get("cc", []))
        mail.BCC = _join_recipients(report_settings.get("bcc", []))
        mail.Subject = _format_email_text(
            template=report_settings.get("subject", report_name),
            report_name=report_name,
            generated_files=generated_files,
            file_links=[],
        )

        use_links = str(report_settings.get("delivery", "")).strip().lower() == "link"
        file_links = (
            build_sharepoint_links(
                files=generated_files,
                sharepoint_settings=email_settings.get("sharepoint", {}),
                base_dir=base_dir,
            )
            if use_links
            else []
        )
        if use_links and file_links:
            mail.Body = _format_email_text(
                template=report_settings.get("body", ""),
                report_name=report_name,
                generated_files=generated_files,
                file_links=file_links,
            )
        else:
            mail.Body = _format_email_text(
                template=report_settings.get("body", ""),
                report_name=report_name,
                generated_files=generated_files,
                file_links=[],
            )
            for file_path in generated_files:
                mail.Attachments.Add(str(file_path))

        mail.Display(False)
    except Exception as exc:
        print(f"Outlook draft skipped for {report_name}: {exc}")
        return False

    return True


def build_sharepoint_links(
    files: list[Path],
    sharepoint_settings: dict[str, Any],
    base_dir: Path,
) -> list[str]:
    sync_folder = str(sharepoint_settings.get("sync_folder", "")).strip()
    web_url = str(sharepoint_settings.get("web_url", "")).strip()
    if not sync_folder or not web_url:
        return []

    sync_root = resolve_path(sync_folder, base_dir).resolve()
    base_url = web_url.rstrip("/")
    links: list[str] = []

    for file_path in files:
        resolved_file = file_path.resolve()
        try:
            relative_path = resolved_file.relative_to(sync_root)
        except ValueError:
            return []

        quoted_relative = "/".join(
            quote(part)
            for part in relative_path.parts
        )
        links.append(f"{base_url}/{quoted_relative}")

    return links


def _matching_report_files(
    generated_files: list[Path],
    file_prefixes: Any,
) -> list[Path]:
    prefixes = _as_list(file_prefixes)
    if not prefixes:
        return []

    normalized_prefixes = tuple(prefix.upper() for prefix in prefixes)
    return [
        file_path
        for file_path in generated_files
        if file_path.name.upper().startswith(normalized_prefixes)
    ]


def _format_email_text(
    template: str,
    report_name: str,
    generated_files: list[Path],
    file_links: list[str],
) -> str:
    file_names = "\n".join(file_path.name for file_path in generated_files)
    links = "\n".join(file_links)
    return str(template).format(
        report_name=report_name,
        file_count=len(generated_files),
        file_names=file_names,
        file_links=links,
    )


def _join_recipients(
    value: Any,
) -> str:
    return "; ".join(_as_list(value))


def _as_list(
    value: Any,
) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(";") if part.strip()]
    if isinstance(value, list | tuple | set):
        return [str(part).strip() for part in value if str(part).strip()]
    return [str(value).strip()] if str(value).strip() else []
