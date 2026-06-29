from __future__ import annotations

from pathlib import Path

from app.core.models import ArchiveStatus
from app.core.models import Element
from app.reports.report_utils import archive_existing_reports
from app.reports.report_utils import get_date_folder
from app.reports.report_utils import get_date_folder_path
from app.reports.report_utils import make_writable
from app.reports.report_utils import safe_release_name
from app.reports.report_utils import sort_elements


def test_safe_release_name_replaces_unsafe_chars() -> None:
    """Verifies safe release name replaces unsafe chars."""
    assert safe_release_name('REL 2026/06') == 'REL_2026_06'


def test_get_date_folder_creates_folder(tmp_path: Path) -> None:
    """Verifies get date folder creates folder."""
    folder=get_date_folder('REL1', tmp_path)
    assert folder.exists()
    assert folder.parent.name == 'REL1'


def test_get_date_folder_path_does_not_create_folder(tmp_path: Path) -> None:
    """Verifies displaying the default report path has no filesystem side effect."""
    folder = get_date_folder_path('REL1', tmp_path)
    assert not folder.exists()
    assert folder.parent.name == 'REL1'


def test_archive_existing_reports_moves_files(tmp_path: Path) -> None:
    """Verifies archive existing reports moves files."""
    report=tmp_path/'report.csv'
    report.write_text('data', encoding='utf-8')
    archive_existing_reports(tmp_path)
    assert not report.exists()
    assert (tmp_path/'History'/'report.csv').exists()
    make_writable(tmp_path/'History'/'report.csv')


def test_archive_existing_reports_keeps_existing_history_file(tmp_path: Path) -> None:
    """Verifies archive existing reports keeps existing history file."""
    history = tmp_path / 'History'
    history.mkdir()
    existing = history / 'report.csv'
    existing.write_text('old', encoding='utf-8')
    report = tmp_path / 'report.csv'
    report.write_text('new', encoding='utf-8')

    archive_existing_reports(tmp_path)

    archived_files = sorted(history.glob('report*.csv'))
    assert len(archived_files) == 2
    assert existing.read_text(encoding='utf-8') == 'old'
    for archived_file in archived_files:
        make_writable(archived_file)


def test_sort_elements_excludes_hidden_and_orders_errors_first() -> None:
    """Verifies sort elements excludes hidden and orders errors first."""
    error=Element(release='REL', project='ABC', element='ZZZ', type='OCOB', archive_status=ArchiveStatus.POTENTIAL_MISSING_ARCHIVE)
    info=Element(release='REL', project='ABC', element='AAA', type='OCOB')
    hidden=Element(release='REL', project='ABC', element='BBB', type='OCOB', visible=False)
    assert sort_elements([info, hidden, error]) == [error, info]
