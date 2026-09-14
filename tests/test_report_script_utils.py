from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

from scripts.report_script_utils import build_sharepoint_links
from scripts.report_script_utils import create_configured_email_drafts


class FakeAttachments:
    def __init__(self) -> None:
        self.paths: list[str] = []

    def Add(
        self,
        path: str,
    ) -> None:
        self.paths.append(path)


class FakeMail:
    def __init__(self) -> None:
        self.To = ""
        self.CC = ""
        self.BCC = ""
        self.Subject = ""
        self.Body = ""
        self.Attachments = FakeAttachments()
        self.displayed = False

    def Display(
        self,
        modal: bool,
    ) -> None:
        self.displayed = not modal


class FakeOutlook:
    def __init__(self) -> None:
        self.mail = FakeMail()

    def CreateItem(
        self,
        _item_type: int,
    ) -> FakeMail:
        return self.mail


def install_fake_outlook(
    monkeypatch,
) -> FakeOutlook:
    fake_outlook = FakeOutlook()
    win32com_module = ModuleType("win32com")
    client_module = ModuleType("win32com.client")
    client_module.Dispatch = lambda _name: fake_outlook
    win32com_module.client = client_module

    monkeypatch.setitem(
        sys.modules,
        "win32com",
        win32com_module,
    )
    monkeypatch.setitem(
        sys.modules,
        "win32com.client",
        client_module,
    )

    return fake_outlook


def test_build_sharepoint_links_uses_relative_synced_path(tmp_path: Path) -> None:
    """Verifies synced SharePoint files can be converted into web links."""
    sync_folder = tmp_path / "SharePoint"
    report = sync_folder / "Daily Reports" / "report file.xlsx"
    report.parent.mkdir(parents=True)
    report.write_text("data", encoding="utf-8")

    links = build_sharepoint_links(
        files=[report],
        sharepoint_settings={
            "sync_folder": str(sync_folder),
            "web_url": "https://contoso.sharepoint.com/sites/Reports/Shared Documents",
        },
        base_dir=tmp_path,
    )

    assert links == [
        "https://contoso.sharepoint.com/sites/Reports/Shared Documents/Daily%20Reports/report%20file.xlsx"
    ]


def test_create_configured_email_drafts_attaches_matching_files(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Verifies enabled email settings open a draft with matching attachments."""
    fake_outlook = install_fake_outlook(monkeypatch)
    report = tmp_path / "Global_Resync_14_SEP_2026.xlsx"
    report.write_text("data", encoding="utf-8")

    created = create_configured_email_drafts(
        settings={
            "email": {
                "enabled": True,
                "reports": {
                    "Global Resync": {
                        "enabled": True,
                        "to": ["team@example.com"],
                        "cc": "lead@example.com",
                        "subject": "{report_name} ready",
                        "body": "Files:\n{file_names}",
                        "delivery": "attachment",
                        "file_prefixes": ["Global_Resync_"],
                    }
                },
            }
        },
        generated_files=[report],
        base_dir=tmp_path,
    )

    assert created == ["Global Resync"]
    assert fake_outlook.mail.To == "team@example.com"
    assert fake_outlook.mail.CC == "lead@example.com"
    assert fake_outlook.mail.Subject == "Global Resync ready"
    assert report.name in fake_outlook.mail.Body
    assert fake_outlook.mail.Attachments.paths == [str(report)]
    assert fake_outlook.mail.displayed is True


def test_create_configured_email_drafts_uses_sharepoint_links(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Verifies link delivery puts SharePoint links in the draft body."""
    fake_outlook = install_fake_outlook(monkeypatch)
    sync_folder = tmp_path / "SharePoint"
    report = sync_folder / "FIXP_Daily_Stats_14_SEP_2026.xlsx"
    report.parent.mkdir(parents=True)
    report.write_text("data", encoding="utf-8")

    created = create_configured_email_drafts(
        settings={
            "email": {
                "enabled": True,
                "sharepoint": {
                    "sync_folder": str(sync_folder),
                    "web_url": "https://contoso.sharepoint.com/sites/Reports/Documents",
                },
                "reports": {
                    "FIXP Daily Stats": {
                        "enabled": True,
                        "to": "fixp@example.com",
                        "subject": "{report_name}",
                        "body": "Links:\n{file_links}",
                        "delivery": "link",
                        "file_prefixes": ["FIXP_Daily_Stats_"],
                    }
                },
            }
        },
        generated_files=[report],
        base_dir=tmp_path,
    )

    assert created == ["FIXP Daily Stats"]
    assert "https://contoso.sharepoint.com/sites/Reports/Documents/FIXP_Daily_Stats_14_SEP_2026.xlsx" in fake_outlook.mail.Body
    assert fake_outlook.mail.Attachments.paths == []
