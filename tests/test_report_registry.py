from __future__ import annotations
from pathlib import Path
import pytest
from openpyxl import load_workbook
from app.core.app_state import AppState
from app.core.models import Element, InventoryIssue, ReleaseEffort, ScheduleStatus
from app.reports.report_registry import ReportRegistry
from app.reports.report_utils import make_writable
from app.services.mainframe_location_service import MainframeLocationService
from app.services.stats_service import StatsService

def make_registry(location_service=None) -> ReportRegistry:
    stats=StatsService(workload_settings={"default_thread_count":1,"type_categories":{"JCL":["JCL"],"NON_COMPILE":["PROC"],"COBOL":["OCOB"],"APS":["OAPS"],"X_ELEMENTS":["XML"],"LINKDECK":["LINK"]},"types_per_hour_per_thread":{"PROD":{"JCL":30,"NON_COMPILE":20,"COBOL":10,"APS":5,"X_ELEMENTS":10,"LINKDECK":10}}})
    return ReportRegistry(
        stats_service=stats,
        location_service_provider=lambda: location_service,
    )

def make_location_line(element: str, type_: str, env: str, version: str, ccid: str) -> str:
    fields=[(element,8),(type_,8),("SYSTEM01",8),("SUB1",4),(env,5),("2026/06/22",10),("12:00:00:00",11),(version,5),("USER01",8),(ccid,7),("COMMENTS",40)]
    return " ".join(value.ljust(width)[:width] for value,width in fields)

def make_location_service(tmp_path: Path) -> MainframeLocationService:
    path=tmp_path/"locations.txt"
    path.write_text(
        "\n".join(
            [
                make_location_line("PGM001","OCOB","DEVL1","01.01","CCID01"),
                make_location_line("PGM001","OCOB","QUAL1","01.02","CCID02"),
            ]
        ),
        encoding="cp1252",
    )
    return MainframeLocationService().load_file(path)

def test_get_names_contains_core_reports() -> None:
    names=make_registry().get_names()
    assert 'Issues Report' in names and 'Effort Summary Report' in names and 'Release Estimate Report' in names and 'Release Inventory Report' in names and 'OSG/COPS Report' in names and 'Resync Report' in names

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

def test_generate_resync_report_csv(tmp_path: Path) -> None:
    state=AppState(release='REL1', mode='PROD', thread_count=1)
    state.loaded_elements=[Element(release='REL1', project='ABC', element='PGM001', type='OCOB')]
    output=make_registry(make_location_service(tmp_path)).generate('Resync Report','csv',state,tmp_path,True)
    assert output is not None and output.exists()
    assert "Higher version exists" in output.read_text(encoding="utf-8")
    make_writable(output)

def test_generate_resync_report_xlsx(tmp_path: Path) -> None:
    state=AppState(release='REL1', mode='PROD', thread_count=1)
    state.loaded_elements=[Element(release='REL1', project='ABC', element='PGM001', type='OCOB')]
    output=make_registry(make_location_service(tmp_path)).generate('Resync Report','xlsx',state,tmp_path,True)
    assert output is not None and output.suffix == '.xlsx' and output.exists()
    make_writable(output)

def test_generate_resync_report_pdf(tmp_path: Path) -> None:
    state=AppState(release='REL1', mode='PROD', thread_count=1)
    state.loaded_elements=[Element(release='REL1', project='ABC', element='PGM001', type='OCOB')]
    output=make_registry(make_location_service(tmp_path)).generate('Resync Report','pdf',state,tmp_path,True)
    assert output is not None and output.suffix == '.pdf' and output.exists()
    make_writable(output)
