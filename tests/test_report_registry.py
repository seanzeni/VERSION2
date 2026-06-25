from __future__ import annotations
from pathlib import Path
import pytest
from openpyxl import load_workbook
from app.core.app_state import AppState
from app.core.models import Element, InventoryIssue, ReleaseEffort, ScheduleStatus
from app.reports.report_registry import ReportRegistry
from app.reports.report_utils import make_writable
from app.services.stats_service import StatsService

def make_registry() -> ReportRegistry:
    stats=StatsService(workload_settings={"default_thread_count":1,"type_categories":{"JCL":["JCL"],"NON_COMPILE":["PROC"],"COBOL":["OCOB"],"APS":["OAPS"],"X_ELEMENTS":["XML"],"LINKDECK":["LINK"]},"types_per_hour_per_thread":{"PROD":{"JCL":30,"NON_COMPILE":20,"COBOL":10,"APS":5,"X_ELEMENTS":10,"LINKDECK":10}}})
    return ReportRegistry(stats_service=stats)

def test_get_names_contains_core_reports() -> None:
    names=make_registry().get_names()
    assert 'Issues Report' in names and 'Effort Summary Report' in names and 'Release Estimate Report' in names and 'Release Inventory Report' in names and 'OSG/COPS Report' in names

def test_unknown_report_raises_key_error() -> None:
    with pytest.raises(KeyError): make_registry().create('Missing Report')

def test_generate_issues_report_csv(tmp_path: Path) -> None:
    state=AppState(release='REL1', mode='PROD', thread_count=1); state.loaded_elements=[Element(release='REL1', project='ABC', element='PGM001', type='OCOB')]
    output=make_registry().generate('Issues Report','csv',state,tmp_path,True)
    assert output is not None and output.exists()
    make_writable(output)

def test_generate_issues_report_xlsx_includes_glossary_sheet(tmp_path: Path) -> None:
    state = AppState(release="REL1", mode="PROD", thread_count=1)
    state.loaded_elements = [
        Element(release="REL1", project="ABC", element="PGM001", type="OCOB")
    ]
    output = make_registry().generate("Issues Report", "xlsx", state, tmp_path, True)
    assert output is not None and output.suffix == ".xlsx" and output.exists()
    workbook = load_workbook(output, read_only=True)
    assert "Issues Report" in workbook.sheetnames
    assert "Issues Report Status Glossary" in workbook.sheetnames
    workbook.close()
    make_writable(output)


def test_generate_effort_summary_xlsx(tmp_path: Path) -> None:
    state = AppState(release="REL1", mode="PROD", thread_count=1)
    state.loaded_elements = [
        Element(release="REL1", project="ABC", element="PGM001", type="OCOB")
    ]
    output = make_registry().generate(
        "Effort Summary Report",
        "xlsx",
        state,
        tmp_path,
        True,
    )
    assert output is not None and output.suffix == ".xlsx" and output.exists()
    make_writable(output)


def test_generate_pdf_not_implemented() -> None:
    with pytest.raises(NotImplementedError): make_registry().generate('Issues Report','pdf',AppState(),Path('.'),True)

def test_generate_effort_summary_pdf(tmp_path: Path) -> None:
    state=AppState(release='REL1', mode='PROD', thread_count=1)
    state.loaded_elements=[Element(release='REL1', project='ABC', element='PGM001', type='OCOB')]
    output=make_registry().generate('Effort Summary Report','pdf',state,tmp_path,True)
    assert output is not None and output.suffix == '.pdf' and output.exists()
    make_writable(output)

def test_generate_release_estimate_pdf(tmp_path: Path) -> None:
    state=AppState(release='REL1', mode='PROD', thread_count=1)
    state.loaded_elements=[Element(release='REL1', project='ABC', element='PGM001', type='OCOB')]
    state.effort_dates={'ABC':'2026-06-22'}
    output=make_registry().generate('Release Estimate Report','pdf',state,tmp_path,True)
    assert output is not None and output.suffix == '.pdf' and output.exists()
    make_writable(output)

def test_generate_release_inventory_pdf(tmp_path: Path) -> None:
    state=AppState(release='REL1', mode='PROD', thread_count=1)
    state.inventory_issues=[
        InventoryIssue(
            release='REL1',
            effort_id='ABC',
            issue_type=ScheduleStatus.SQL_EXPECTED_INVENTORY_MISSING,
            reason='Missing inventory',
        )
    ]
    state.release_efforts=[ReleaseEffort(effort_id='ABC')]
    output=make_registry().generate('Release Inventory Report','pdf',state,tmp_path,True)
    assert output is not None and output.suffix == '.pdf' and output.exists()
    make_writable(output)

def test_generate_osg_cops_pdf(tmp_path: Path) -> None:
    state=AppState(release='REL1', mode='PROD', thread_count=1)
    state.loaded_elements=[
        Element(
            release='REL1',
            project='ABC',
            element='OPGM001',
            type='OCOB',
            source_row={'Submitter':'USER1','Application':'APP','Package':'PKG','Area':'AREA','Service':'SVC'},
        )
    ]
    output=make_registry().generate('OSG/COPS Report','pdf',state,tmp_path,True)
    assert output is not None and output.suffix == '.pdf' and output.exists()
    make_writable(output)
